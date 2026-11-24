import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import OPENROUTER_API_KEY
from app.services.embedding_service import normalize_name
from app.services.llm_service import get_llm_provider
from app.services.query_embedding_service import embed_query
from app.services.stat_vectors import SeasonVectors, describe, load_season


SYSTEM_PROMPT = """You are a basketball scouting analyst. Answer only from the supplied
database evidence. Be concise, compare players when useful, and mention concrete statistics
that appear in the evidence. Never invent a statistic. If the evidence is insufficient, say
so explicitly. Refer to sources by player name and season."""


SIMILAR_WORDS = re.compile(r"\b(similar|like|comparable|resembl\w*|comparison|replace\w*|alternative\w*)\b", re.I)
YOUNG_WORDS = re.compile(r"\b(young\w*|prospects?|rising)\b", re.I)
YOUNG_MAX_AGE = 24


# Words in a question that point at a measurable skill.
SKILL_WORDS = [
    (re.compile(r"\b(rim protect\w*|shot[- ]block\w*|blocks?)\b", re.I), ["blocks"]),
    (re.compile(r"\brebound\w*\b", re.I), ["rebounds"]),
    (re.compile(r"\b(playmak\w*|pass\w*|assists?|facilitat\w*)\b", re.I), ["assists"]),
    (re.compile(r"\b(steals?|perimeter defen\w*)\b", re.I), ["steals"]),
    (re.compile(r"\b(defen[cs]\w*|defenders?)\b", re.I), ["steals", "blocks"]),
    (re.compile(r"\b(three[- ]point\w*|3[- ]?point\w*|threes|shooters?|spacing)\b", re.I), ["three_point_attempts", "three_point_shrunk"]),
    (re.compile(r"\b(scor(er|ers|ing)|points)\b", re.I), ["points"]),
    (re.compile(r"\bfree throws?\b", re.I), ["free_throw_shrunk"]),
    (re.compile(r"\b(efficien\w*|finish\w*)\b", re.I), ["field_goal_pct"]),
]
ROLE_WORDS = [(re.compile(rf"\b{role}s?\b", re.I), role) for role in ("guard", "forward", "center")]


def asked_skills(question: str) -> list[str]:
    plain = re.sub(r"\bthree[- ]points?\b", "threes", question, flags=re.I)
    return list(dict.fromkeys(f for pattern, features in SKILL_WORDS if pattern.search(plain) for f in features))


def find_named_players(vectors: SeasonVectors, question: str) -> list[dict]:
    """Players mentioned by full name, or by a capitalised first or last name."""
    plain = normalize_name(question)
    found = [row for row in vectors.rows if re.search(rf"\b{re.escape(normalize_name(row['full_name']))}\b", plain)]
    used = {word for row in found for word in normalize_name(row["full_name"]).split()}

    words = re.findall(r"[^\W\d_][\w'\-]*", question)
    for position, word in enumerate(words):
        key = normalize_name(word.removesuffix("'s"))
        # The first word of a sentence is capitalised anyway, so it proves nothing.
        if len(key) < 4 or not word[0].isupper() or key in used or key in STOP_NAMES:
            continue
        matches = [row for row in vectors.rows if key in normalize_name(row["full_name"]).split()]
        if not matches or (position == 0 and len(matches) > 1):
            continue
        best = max(matches, key=lambda row: row["points"] or 0)
        found.append(best)
        used.update(normalize_name(best["full_name"]).split())
    return found[:3]


# Names that are also ordinary words or cities in basketball questions.
STOP_NAMES = {"young", "will", "best", "which", "who", "what", "houston", "jordan", "west", "love", "max"}


def retrieve_context(db: Session, question: str, season: str | None, limit: int):
    vectors = load_season(db, season)
    if vectors is None:
        return []
    max_age = YOUNG_MAX_AGE if YOUNG_WORDS.search(question) else None
    sources: list[dict] = []
    seen: set[int] = set()

    def add(row: dict, similarity: float):
        if row["player_id"] in seen or len(sources) >= limit:
            return
        seen.add(row["player_id"])
        sources.append(
            {
                "player_id": row["player_id"],
                "full_name": row["full_name"],
                "season": vectors.season,
                "source_text": describe(vectors, row["player_id"]),
                "similarity": similarity,
            }
        )

    # 1. Anyone named in the question is always part of the evidence.
    named = find_named_players(vectors, question)
    for row in named:
        add(row, 1.0)

    # 2. "Similar to X" is a statistical question, answered by the stat vectors.
    if named and SIMILAR_WORDS.search(question):
        for row, similarity in vectors.neighbours(named[0]["player_id"]):
            if max_age is None or (row["age"] is not None and row["age"] <= max_age):
                add(row, similarity)

    # 3. Skill questions ("best rim protectors") rank on the skills themselves.
    skills = asked_skills(question)
    if skills and not named:
        roles = [role for pattern, role in ROLE_WORDS if pattern.search(question)]
        for row, score in vectors.leaders(skills):
            if max_age is not None and (row["age"] is None or row["age"] > max_age):
                continue
            if roles and not any(role in (row["position"] or "").lower() for role in roles):
                continue
            add(row, score)

    # 4. Everything else is filled by semantic search over the season descriptions.
    if len(sources) < limit:
        sql = text(
            """
            select pe.player_id, 1 - (pe.embedding <=> cast(:embedding as vector)) as similarity
            from player_embeddings pe
            join player_season_stats ps on ps.player_id = pe.player_id and ps.season = pe.season
            left join player_profiles pp on pp.player_id = pe.player_id
            where pe.season = :season
              and (:max_age is null or pp.age <= :max_age)
            order by pe.embedding <=> cast(:embedding as vector)
            limit :limit
            """
        )
        matches = db.execute(
            sql,
            {
                "embedding": embed_query(question),
                "season": vectors.season,
                "max_age": max_age,
                "limit": limit + len(sources),
            },
        ).mappings()
        for match in matches:
            add(vectors.rows[vectors.index[match["player_id"]]], match["similarity"])
    return sources


def answer_question(db: Session, question: str, season: str | None, limit: int):
    sources = retrieve_context(db, question, season, limit)
    if not OPENROUTER_API_KEY:
        # Without a language model the retrieved evidence is still useful on its own.
        return {"answer": "", "provider": "none", "model": "", "sources": sources}
    context = "\n\n".join(
        f"SOURCE {index}: {row['full_name']} ({row['season']})\n{row['source_text']}"
        for index, row in enumerate(sources, start=1)
    )
    provider = get_llm_provider()
    answer = provider.generate(
        SYSTEM_PROMPT,
        f"Question: {question}\n\nRetrieved database evidence:\n{context}",
    )
    return {
        "answer": answer,
        "provider": provider.name,
        "model": provider.model,
        "sources": sources,
    }
