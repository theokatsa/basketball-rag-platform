import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.insight_service import explain_similarity
from app.services.stat_vectors import SeasonVectors, describe, load_season


def normalize_name(value: str) -> str:
    """Lower-case and strip accents, so "Jokic" finds "Jokić"."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def _resolve_reference_player(
    vectors: SeasonVectors, player_id: int | None, player_name: str | None
) -> int | None:
    if player_id is not None:
        return player_id if player_id in vectors.index else None
    needle = normalize_name(player_name or "")
    if not needle:
        return None
    matches = [row for row in vectors.rows if needle in normalize_name(row["full_name"])]
    if not matches:
        return None

    def rank(row):
        name = normalize_name(row["full_name"])
        return (name != needle, not name.startswith(needle), -(row["points"] or 0))

    return min(matches, key=rank)["player_id"]


def search_reference_players(
    db: Session,
    query: str | None,
    season: str | None = None,
    limit: int = 10,
):
    vectors = load_season(db, season)
    if vectors is None:
        return []
    needle = normalize_name(query or "")
    matches = [row for row in vectors.rows if needle in normalize_name(row["full_name"])]
    matches.sort(key=lambda row: -(row["points"] or 0))
    return [
        {"player_id": row["player_id"], "full_name": row["full_name"]} for row in matches[:limit]
    ]


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
    vectors = load_season(db, season)
    if vectors is None:
        return None
    reference_id = _resolve_reference_player(vectors, player_id, player_name)
    if reference_id is None:
        return None

    wanted_position = position.strip().lower() if position else None
    results = []
    for row, similarity in vectors.neighbours(reference_id):
        if is_active is not None and row["is_active"] != is_active:
            continue
        if min_age is not None and (row["age"] is None or row["age"] < min_age):
            continue
        if max_age is not None and (row["age"] is None or row["age"] > max_age):
            continue
        if wanted_position and wanted_position not in (row["position"] or "").lower():
            continue
        results.append(
            {
                "player_id": row["player_id"],
                "full_name": row["full_name"],
                "season": row["season"],
                "source_text": describe(vectors, row["player_id"]),
                "similarity": similarity,
                "age": row["age"],
                "position": row["position"],
                "is_active": row["is_active"],
                "shared_traits": vectors.shared_traits(reference_id, row["player_id"]),
                **explain_similarity(vectors, reference_id, row["player_id"]),
            }
        )
        if len(results) == limit:
            break
    return results


def get_similar_players(db: Session, player_id: int, season: str | None = None, limit: int = 5):
    return search_similar_players(
        db=db,
        player_id=player_id,
        season=season,
        limit=limit,
    ) or []
