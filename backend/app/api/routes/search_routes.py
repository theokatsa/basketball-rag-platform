from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.similar_player_schema import (
    SimilarPlayerPositionOptionResponse,
    SimilarPlayerReferenceOptionResponse,
    SimilarPlayerResponse,
    SimilarPlayerSearchRequest,
)
from app.services.embedding_service import (
    get_search_positions,
    search_reference_players,
    search_similar_players,
)

router = APIRouter(prefix="/search")


@router.get("/reference-players", response_model=list[SimilarPlayerReferenceOptionResponse])
def search_reference_players_route(
    q: str | None = None,
    season: str | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 25))
    return search_reference_players(db, q, season, safe_limit)


@router.get("/positions", response_model=list[SimilarPlayerPositionOptionResponse])
def search_positions_route(db: Session = Depends(get_db)):
    return get_search_positions(db)


@router.post("/similar-players", response_model=list[SimilarPlayerResponse])
def search_similar_players_route(
    payload: SimilarPlayerSearchRequest,
    db: Session = Depends(get_db),
):
    try:
        results = search_similar_players(
            db=db,
            player_id=payload.player_id,
            player_name=payload.player_name,
            season=payload.season,
            limit=payload.limit,
            min_age=payload.min_age,
            max_age=payload.max_age,
            position=payload.position,
            is_active=payload.is_active,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to query the database for similarity search.",
        ) from exc

    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No embedding found for the requested player.",
        )

    return results
