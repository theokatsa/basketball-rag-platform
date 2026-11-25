"""Finds evidence for a question, several ways, so that they can be compared.

keyword  PostgreSQL full-text search
vector   nearest embeddings (pgvector, cosine, HNSW)
hybrid   both lists merged with Reciprocal Rank Fusion
planned  the query plan decides: exact filters and rankings, statistical neighbours, and
         hybrid search for whatever the plan leaves open
rules    planned without the semantic skill router, to measure what the router adds
"""

from __future__ import annotations

from sqlalchemy import text

from app.services.cache import cached, rows
from app.services.query_embedding_service import MODEL_NAME, embed_query
from app.services.query_planner import Plan, make_plan
from app.services.skill_router import MIN_SIMILARITY, OVERRULE_SIMILARITY, route
from app.services.stat_vectors import FEATURES, load_season
from app.services.text_utils import normalize_name

MODES = ("keyword", "vector", "hybrid", "rules", "planned")
POOL = 50  # candidates taken from each list before merging
RRF_K = 60  # the usual constant: a high rank in one list does not drown out the other
MIN_EVIDENCE_SIMILARITY = 0.30  # below this even the nearest document is about something else
COLUMNS = "d.id, d.doc_key, d.kind, d.entity, d.season, d.title, d.content, d.player_ids, d.team_ids"
TEAM_METRICS = {"def_rating", "off_rating", "wins", "three_pct", "threes", "pace", "rebounds", "assists", "turnovers"}
NUMBERS = {"points", "rebounds", "assists", "steals", "blocks", "turnovers", "minutes", "games_played", "field_goal_pct", "three_point_pct", "free_throw_pct"}
OPERATORS = {">=", ">", "<=", "<"}
PERCENT = {"field_goal_pct", "three_point_pct", "free_throw_pct"}


def list_teams(db) -> list[dict]:
    return cached("teams", lambda: rows(db, text("select nba_team_id, full_name, city, nickname from teams")))


def plan_question(db, question: str, season: str | None, router: bool = True) -> tuple[Plan, str] | None:
    vectors = load_season(db, season)
    if vectors is None:
        return None
    plan = make_plan(question, vectors.season, vectors.rows, list_teams(db))
    # Paraphrases: let the embedding choose the skill when the words did not, or clearly chose badly.
    if router and (plan.intent == "open" or (plan.intent == "ranking" and not plan.thresholds)):
        skills, similarity = route(question)
        if similarity >= (OVERRULE_SIMILARITY if plan.skills else MIN_SIMILARITY):
            plan.intent, plan.kinds, plan.skills = "ranking", ["player_season"], skills
    return plan, vectors.season


def _scope(plan: Plan | None, season: str, people: bool = True) -> tuple[str, dict]:
    """The plan's exact constraints as SQL. Column names come from fixed lists, values are bound."""
    where, params = ["d.season = :season"], {"season": season}
    if plan is None:
        return where[0], params
    if plan.kinds:
        where.append("d.kind = any(:kinds)")
        params["kinds"] = plan.kinds
    if plan.teams:
        # A game between two teams must involve both; otherwise any of the teams will do.
        where.append("d.team_ids @> :teams" if plan.kinds == ["game"] else "d.team_ids && :teams")
        params["teams"] = [t["nba_team_id"] for t in plan.teams]
    if plan.players and people:
        where.append("d.player_ids && cast(:players as bigint[])")
        params["players"] = [p["player_id"] for p in plan.players]
    if plan.kinds == ["player_season"]:
        if plan.roles:
            where.append("(" + " or ".join(f"d.meta->>'position' like :role{i}" for i in range(len(plan.roles))) + ")")
            params |= {f"role{i}": f"%{role}%" for i, role in enumerate(plan.roles)}
        if plan.min_age is not None:
            where.append("(d.meta->>'age')::float >= :min_age")
            params["min_age"] = plan.min_age
        if plan.max_age is not None:
            where.append("(d.meta->>'age')::float <= :max_age")
            params["max_age"] = plan.max_age
        for i, (stat, op, value) in enumerate(plan.thresholds):
            if stat in NUMBERS and op in OPERATORS:
                where.append(f"(d.meta->>'{stat}')::float {op} :limit{i}")
                params[f"limit{i}"] = value / 100 if stat in PERCENT else value
    return " and ".join(where), params


def search(db, question: str, season: str, limit: int, mode: str = "hybrid", plan: Plan | None = None, people: bool = True) -> list[dict]:
    """Keyword, vector or hybrid search inside the plan's constraints."""
    where, params = _scope(plan, season, people)
    params |= {"limit": limit, "pool": POOL}
    lists = []
    if mode in ("vector", "hybrid"):
        stored = cached("index_model", lambda: db.execute(text("select embedding_model from rag_index_info")).scalar())
        if stored != MODEL_NAME:
            raise RuntimeError(f"The index was built with {stored}, but EMBEDDING_MODEL is {MODEL_NAME}. Run scripts/build_rag_index.py.")
        # Filtered HNSW can run out of candidates; iterative scan keeps going until enough pass.
        db.execute(text("set local hnsw.iterative_scan = strict_order"))
        db.execute(text("set local hnsw.ef_search = 100"))
        params["embedding"] = embed_query(question)
        lists.append(f"""dense as materialized (select d.id, 1 - (d.embedding <=> cast(:embedding as vector)) as similarity from rag_documents d
            where {where} order by d.embedding <=> cast(:embedding as vector) limit :pool)""")
    if mode in ("keyword", "hybrid"):
        # Any word may match; ts_rank_cd favours documents with more of them close together.
        params["words"] = normalize_name(question)
        lists.append(f"""words as (select replace(plainto_tsquery('english', :words)::text, '&', '|')::tsquery as q),
            sparse as materialized (select d.id, ts_rank_cd(d.tsv, words.q, 1) as score from rag_documents d, words
            where {where} and d.tsv @@ words.q order by score desc, d.id limit :pool)""")
    ranked = []
    if mode in ("vector", "hybrid"):
        ranked.append("select id, similarity, row_number() over (order by similarity desc) as r from dense")
    if mode in ("keyword", "hybrid"):
        ranked.append("select id, null::float8 as similarity, row_number() over (order by score desc, id) as r from sparse")
    sql = f"""with {', '.join(lists)}, merged as (
        select id, max(similarity) as similarity, sum(1.0 / ({RRF_K} + r)) as fused from ({' union all '.join(ranked)}) l group by id)
        select {COLUMNS}, m.similarity, m.fused::float8 as score from merged m join rag_documents d on d.id = m.id order by m.fused desc, d.id limit :limit"""
    return rows(db, text(sql), params)


def _ranking(db, plan: Plan, season: str, limit: int) -> list[dict]:
    """Players inside the constraints, best first: the mean of the asked skills blended with the weakest one."""
    where, params = _scope(plan, season)
    skills = [s for s in plan.skills if s in FEATURES]
    if skills:
        z = [f"(d.meta->>'z_{s}')::float" for s in skills]
        score = f"0.5 * ({' + '.join(z)}) / {len(z)} + 0.5 * least({', '.join(z)})"
    elif plan.thresholds and plan.thresholds[0][0] in NUMBERS:
        score = f"(d.meta->>'{plan.thresholds[0][0]}')::float" + ("" if plan.thresholds[0][1].startswith(">") else " * -1")
    else:
        score = "(d.meta->>'minutes')::float"
    return rows(db, text(f"""select {COLUMNS}, null::float8 as similarity, ({score})::float8 as score from rag_documents d
        where {where} and (d.meta->>'qualified')::boolean order by score desc, d.id limit :limit"""), params | {"limit": limit})


def _team_ranking(db, plan: Plan, season: str, limit: int) -> list[dict]:
    metric, descending = plan.order
    if metric not in TEAM_METRICS:
        return []
    where, params = _scope(plan, season)
    value = f"(d.meta->>'{metric}')::float"
    return rows(db, text(f"""select {COLUMNS}, null::float8 as similarity, {value}::float8 as score from rag_documents d
        where {where} order by {value} {'desc' if descending else 'asc'}, d.id limit :limit"""), params | {"limit": limit})


def stat_neighbours(db, player_id: int, season: str, limit: int, plan: Plan | None = None, extra: str = "true", extra_params: dict | None = None) -> list[dict]:
    """Nearest statistical vectors in pgvector, with the filters applied in the same query."""
    where, params = _scope(plan, season, people=False)
    db.execute(text("set local hnsw.iterative_scan = strict_order"))
    db.execute(text("set local hnsw.ef_search = 100"))
    # power(): in PostgreSQL -x ^ 2 means (-x) ^ 2. Distance is the root mean square gap in z-scores.
    return rows(db, text(f"""
        select {COLUMNS}, d.player_ids[1] as player_id, exp(-power(v.z <-> me.z, 2) / {2 * len(FEATURES)}) as similarity, exp(-power(v.z <-> me.z, 2) / {2 * len(FEATURES)}) as score
        from (select z from player_stat_vectors where player_id = :me and season = :season) me
        join player_stat_vectors v on v.season = :season and v.player_id <> :me and v.qualified
        join rag_documents d on d.kind = 'player_season' and d.entity = 'player:' || v.player_id
        where {where} and {extra} order by v.z <-> me.z limit :limit
    """), params | {"me": player_id, "limit": limit} | (extra_params or {}))


def documents_for(db, players: list[int], kinds: list[str], season: str) -> list[dict]:
    """The documents about these players, in the order the players were mentioned."""
    return rows(db, text(f"""select {COLUMNS}, null::float8 as similarity, 1.0::float8 as score from rag_documents d
        where d.season = :season and d.kind = any(:kinds) and d.entity = any(:entities)
        order by array_position(:entities, d.entity), array_position(:kinds, d.kind)"""),
        {"season": season, "kinds": kinds, "entities": [f"player:{p}" for p in players]})


def _planned(db, question: str, plan: Plan, season: str, limit: int) -> list[dict]:
    ids = [p["player_id"] for p in plan.players]
    if plan.intent == "out_of_scope":
        return []
    if plan.intent == "similar":
        # Imported here: similarity_service needs tables that are loaded later.
        from app.services.similarity_service import neighbours

        found = neighbours(db, ids[0], "overall", (limit - 1) * 4, plan.min_age, plan.max_age, team_id=plan.teams[0]["nba_team_id"] if plan.teams else None)
        if plan.roles:
            positions = {r["player_id"]: r["position"] or "" for r in load_season(db, season).rows}
            found = [r for r in found if any(role in positions.get(r["player_id"], "") for role in plan.roles)]
        return documents_for(db, ids[:1], ["player_season"], season) + [{**r, "score": r["similarity"]} for r in found[: limit - 1]]
    if plan.intent == "ranking":
        return _ranking(db, plan, season, limit)
    if plan.intent == "team_ranking":
        return _team_ranking(db, plan, season, limit)
    if plan.intent == "lookup" and ids and plan.kinds != ["pairs"] and plan.kinds != ["game"]:
        found = documents_for(db, ids, plan.kinds, season)
        if plan.kinds != ["player_season"]:  # the season line gives the specialised document its context
            found += documents_for(db, ids, ["player_season"], season)
        return found[:limit]
    if plan.intent == "lookup":
        return search(db, question, season, limit, "hybrid", plan, people=False)
    found = search(db, question, season, limit, "hybrid")
    if max((r["similarity"] or 0 for r in found), default=0) < MIN_EVIDENCE_SIMILARITY:
        plan.intent, plan.reason = "out_of_scope", "Nothing in the database is close to this question."
        return []
    return found


def retrieve(db, question: str, season: str | None, limit: int, mode: str = "planned") -> tuple[list[dict], Plan | None]:
    planned = plan_question(db, question, season, router=mode != "rules")
    if planned is None:
        return [], None
    plan, season = planned
    if mode not in ("planned", "rules"):
        return search(db, question, season, limit, mode), None
    return _planned(db, question, plan, season, limit), plan
