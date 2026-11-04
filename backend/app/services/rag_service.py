from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.llm_service import get_llm_provider
from app.services.query_embedding_service import embed_query


SYSTEM_PROMPT = """You are a basketball scouting analyst. Answer only from the supplied
database evidence. Be concise, compare players when useful, and mention concrete statistics
that appear in the evidence. Never invent a statistic. If the evidence is insufficient, say
so explicitly. Refer to sources by player name and season."""


def retrieve_context(db: Session, question: str, season: str | None, limit: int):
    query_embedding = embed_query(question)
    sql = text(
        """
        select pe.player_id,
               p.full_name,
               pe.season,
               pe.source_text,
               1 - (pe.embedding <=> cast(:embedding as vector)) as similarity
        from player_embeddings pe
        join players p on p.id = pe.player_id
        where (:season is null or pe.season = :season)
                    and exists (
                        select 1
                        from player_season_stats ps
                        where ps.player_id = pe.player_id
                            and ps.season = pe.season
                    )
        order by pe.embedding <=> cast(:embedding as vector)
        limit :limit
        """
    )
    return db.execute(
        sql, {"embedding": query_embedding, "season": season, "limit": limit}
    ).mappings().all()


def answer_question(db: Session, question: str, season: str | None, limit: int):
    sources = retrieve_context(db, question, season, limit)
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
