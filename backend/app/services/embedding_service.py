from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.player_service import get_player_by_id


def get_similar_players(db: Session, player_id: int, season: str | None = None, limit: int = 5):
    player = get_player_by_id(db, player_id)
    if not player:
        return []

    base_embedding_sql = text(
        """
        select embedding
        from player_embeddings
        where player_id = :player_id
          and (:season is null or season = :season)
        order by created_at desc
        limit 1
        """
    )

    base_embedding = db.execute(
        base_embedding_sql,
        {"player_id": player_id, "season": season},
    ).scalar()

    if base_embedding is None:
        return []

    query_sql = text(
        """
        select pe.player_id,
               p.full_name,
               pe.season,
               pe.source_text,
               1 - (pe.embedding <=> base.embedding) as similarity
        from player_embeddings pe
                cross join (select cast(:base_embedding as vector) as embedding) base
        join players p on p.id = pe.player_id
                where (:season is null or pe.season = :season)
                    and pe.player_id != :player_id
        order by pe.embedding <=> base.embedding
        limit :limit
        """
    )

    return db.execute(
        query_sql,
                {"player_id": player_id, "season": season, "limit": limit, "base_embedding": base_embedding},
    ).mappings().all()