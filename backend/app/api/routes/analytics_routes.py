from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics_schema import (
    PlayerComparisonItem,
    ShotProfileResponse,
    TopAssisterResponse,
    TopScorerResponse,
)
from app.services.analytics_service import (
    get_player_comparison,
    get_shot_profile,
    get_top_assisters,
    get_top_scorers,
)

router = APIRouter(prefix="/analytics")


@router.get("/top-scorers", response_model=list[TopScorerResponse])
def top_scorers(
    season: str = Query("2024-25"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return get_top_scorers(db, season, limit)


@router.get("/top-assisters", response_model=list[TopAssisterResponse])
def top_assisters(
    season: str = Query("2024-25"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return get_top_assisters(db, season, limit)


@router.get("/player-comparison", response_model=list[PlayerComparisonItem])
def player_comparison(
    player1_id: int,
    player2_id: int,
    season: str = Query("2024-25"),
    db: Session = Depends(get_db),
):
    return get_player_comparison(db, season, player1_id, player2_id)


@router.get("/shot-profile/{player_id}", response_model=list[ShotProfileResponse])
def shot_profile(player_id: int, db: Session = Depends(get_db)):
    return get_shot_profile(db, player_id)
