from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.player_service import get_player_by_id


def _resolve_reference_player(
    db: Session,
    player_id: int | None,
    player_name: str | None,
    season: str | None,
):
    if player_id is not None:
        player = get_player_by_id(db, player_id)
        if not player:
            return None

        return {
            "player_id": player.id,
            "full_name": player.full_name,
        }

    if not player_name:
        return None

    ref_player_sql = text(
        """
        select p.id as player_id,
               p.full_name
        from players p
        join player_embeddings pe on pe.player_id = p.id
        where (:season is null or pe.season = :season)
          and p.full_name ilike :player_name
        order by case
            when lower(p.full_name) = lower(:player_name_exact) then 0
            when lower(p.full_name) like lower(:player_name_prefix) then 1
            else 2
        end,
        length(p.full_name)
        limit 1
        """
    )

    return db.execute(
        ref_player_sql,
        {
            "season": season,
            "player_name": f"%{player_name}%",
            "player_name_exact": player_name,
            "player_name_prefix": f"{player_name}%",
        },
    ).mappings().first()


def search_reference_players(
    db: Session,
    query: str | None,
    season: str | None = None,
    limit: int = 10,
):
    reference_sql = text(
        """
        select p.id as player_id,
               p.full_name
        from players p
        where exists (
            select 1
            from player_embeddings pe
            where pe.player_id = p.id
              and (:season is null or pe.season = :season)
        )
          and (:query is null or p.full_name ilike :query)
        order by p.full_name
        limit :limit
        """
    )

    term = query.strip() if query else ""
    return db.execute(
        reference_sql,
        {
            "season": season,
            "query": f"%{term}%" if term else None,
            "limit": limit,
        },
    ).mappings().all()


def get_search_positions(db: Session):
    positions_sql = text(
        """
        select distinct position
        from player_profiles
        where position is not null
          and btrim(position) <> ''
        order by position
        """
    )
    return db.execute(positions_sql).mappings().all()


def _get_base_embedding(db: Session, reference_player_id: int, season: str | None = None):
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

    return db.execute(
        base_embedding_sql,
        {"player_id": reference_player_id, "season": season},
    ).scalar()


def search_similar_players(
    db: Session,
    player_id: int | None = None,
    player_name: str | None = None,
    season: str | None = None,
    limit: int = 5,
    min_age: int | None = None,
    max_age: int | None = None,
    position: str | None = None,
    is_active: bool | None = None,
):
    reference_player = _resolve_reference_player(db, player_id, player_name, season)
    if not reference_player:
        return None

    reference_player_id = int(reference_player["player_id"])

    base_embedding = _get_base_embedding(db, reference_player_id, season)
    if base_embedding is None:
        return None

    query_sql = text(
        """
        select pe.player_id,
               p.full_name,
               pe.season,
               pe.source_text,
               pp.age,
               pp.position,
               p.is_active,
               1 - (pe.embedding <=> base.embedding) as similarity
        from player_embeddings pe
        cross join (select cast(:base_embedding as vector) as embedding) base
        join players p on p.id = pe.player_id
        left join player_profiles pp on pp.player_id = pe.player_id
        where (:season is null or pe.season = :season)
          and pe.player_id != :reference_player_id
          and (:is_active is null or p.is_active = :is_active)
          and (:min_age is null or pp.age >= :min_age)
          and (:max_age is null or pp.age <= :max_age)
          and (:position is null or pp.position ilike :position)
        order by pe.embedding <=> base.embedding
        limit :limit
        """
    )

    return db.execute(
        query_sql,
        {
            "reference_player_id": reference_player_id,
            "season": season,
            "limit": limit,
            "base_embedding": base_embedding,
            "is_active": is_active,
            "min_age": min_age,
            "max_age": max_age,
            "position": f"%{position.strip()}%" if position else None,
        },
    ).mappings().all()


def get_similar_players(db: Session, player_id: int, season: str | None = None, limit: int = 5):
    return search_similar_players(
        db=db,
        player_id=player_id,
        season=season,
        limit=limit,
    )