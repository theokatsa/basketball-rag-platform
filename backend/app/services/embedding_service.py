from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.insight_service import explain_similarity
from app.services.league_data import people
from app.services.retrieval import stat_neighbours
from app.services.similarity_service import explain, neighbours, table
from app.services.stat_vectors import SeasonVectors, describe, load_season
from app.services.text_utils import normalize_name


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
    team_id: int | None = None,
    kind: str = "overall",
):
    """kind: "overall" or "style" (learned from shots and box scores) or "production" (twelve averages)."""
    vectors = load_season(db, season)
    if vectors is None:
        return None
    reference_id = _resolve_reference_player(vectors, player_id, player_name)
    if reference_id is None:
        return None
    filters = {"min_age": min_age, "max_age": max_age, "position": position, "is_active": is_active, "team_id": team_id}
    if kind == "production":
        found = _by_production(db, vectors, reference_id, limit, **filters)
    else:
        found = neighbours(db, reference_id, kind, limit, **filters)
    styles = table(db)
    results = []
    for match in found:
        other = match["player_id"]
        if other not in vectors.index:  # indexed, but gone from the statistics since
            continue
        row = vectors.rows[vectors.index[other]]
        results.append(
            {
                "player_id": other,
                "full_name": row["full_name"],
                "season": row["season"],
                "source_text": describe(vectors, other),
                "similarity": match["similarity"],
                "age": row["age"],
                "position": row["position"],
                "is_active": row["is_active"],
                "shared_traits": vectors.shared_traits(reference_id, other),
                "archetype": styles.at[other, "archetype"] if other in styles.index else None,
                **explain(db, reference_id, other),
                **(explain_similarity(vectors, reference_id, other) if kind == "production" else {}),
            }
        )
    return results


def _by_production(db, vectors, reference_id, limit, min_age, max_age, position, is_active, team_id):
    conditions, params = ["true"], {}
    for value, name, condition in (
        (min_age, "min_age", "(d.meta->>'age')::float >= :min_age"),
        (max_age, "max_age", "(d.meta->>'age')::float <= :max_age"),
        (team_id, "team_id", "d.team_ids @> array[cast(:team_id as int)]"),
        (position.strip().lower() if position and position.strip() else None, "position", "strpos(lower(d.meta->>'position'), :position) > 0"),
        (is_active, "is_active", "exists (select 1 from players p where p.id = v.player_id and p.is_active = :is_active)"),
    ):
        if value is not None:
            conditions.append(condition)
            params[name] = value
    return stat_neighbours(db, reference_id, vectors.season, limit, extra=" and ".join(conditions), extra_params=params)


YOUNGER_BY = 3  # seasons


def get_similar_players(db: Session, player_id: int, season: str | None = None, limit: int = 5, kind: str = "overall", variant: str = "any"):
    """variant: "younger" by three years or more, or "better" by overall score."""
    if variant == "any":
        return search_similar_players(db=db, player_id=player_id, season=season, limit=limit, kind=kind) or []
    folk = people(db)
    if player_id not in folk.index:
        return []
    me = folk.loc[player_id]
    if variant == "younger":
        return search_similar_players(db=db, player_id=player_id, season=season, limit=limit, kind=kind, max_age=int(me.age) - YOUNGER_BY) or []
    found = search_similar_players(db=db, player_id=player_id, season=season, limit=60, kind=kind) or []
    return [r for r in found if r["player_id"] in folk.index and (folk.at[r["player_id"], "overall_score"] or 0) > (me.overall_score or 0)][:limit]
