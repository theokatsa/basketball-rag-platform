from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.player_directory_schema import PlayerDirectoryRowResponse
from app.schemas.player_game_log_schema import (
    BestGameResponse,
    PlayerGameLogResponse,
    PlayerTotalsResponse,
)
from app.schemas.player_schema import PlayerResponse
from app.schemas.player_season_stats_schema import PlayerSeasonStatsResponse
from app.schemas.player_profile_schema import PlayerProfileResponse
from app.schemas.shot_chart_schema import ShotChartResponse
from app.schemas.similar_player_schema import SimilarPlayerResponse
from app.services.game_service import best_games
from app.services.player_service import (
    get_player_by_id,
    get_players_directory,
    get_player_game_logs,
    get_player_profile,
    get_player_season_stats,
    get_player_shots,
    get_player_totals,
)
from app.services.embedding_service import get_similar_players

router = APIRouter()


@router.get("/players/directory", response_model=list[PlayerDirectoryRowResponse])
def read_players_directory(
    season: str | None = None,
    db: Session = Depends(get_db),
):
    return get_players_directory(db, season)


@router.get("/players/totals", response_model=list[PlayerTotalsResponse])
def read_player_totals(db: Session = Depends(get_db)):
    return get_player_totals(db)


@router.get("/players/best-games", response_model=list[BestGameResponse])
def read_best_games(limit: int = Query(8, ge=1, le=50), db: Session = Depends(get_db)):
    return best_games(db, limit)


@router.get("/players/{player_id}", response_model=PlayerResponse)
def read_player(player_id: int, db: Session = Depends(get_db)):
    player = get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )
    return player


@router.get("/players/{player_id}/season-stats", response_model=list[PlayerSeasonStatsResponse])
def read_player_season_stats(player_id: int, db: Session = Depends(get_db)):
    player = get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )
    return get_player_season_stats(db, player_id)


@router.get("/players/{player_id}/profile", response_model=PlayerProfileResponse)
def read_player_profile(player_id: int, db: Session = Depends(get_db)):
    profile = get_player_profile(db, player_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player profile not found"
        )
    return profile


@router.get("/players/{player_id}/game-logs", response_model=list[PlayerGameLogResponse])
def read_player_game_logs(player_id: int, db: Session = Depends(get_db)):
    player = get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )
    return get_player_game_logs(db, player_id)


@router.get("/players/{player_id}/shots", response_model=list[ShotChartResponse])
def read_player_shots(player_id: int, db: Session = Depends(get_db)):
    player = get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )
    return get_player_shots(db, player_id)


@router.get("/players/{player_id}/similar", response_model=list[SimilarPlayerResponse])
def read_similar_players(
    player_id: int,
    season: str | None = None,
    limit: int = Query(5, ge=1, le=50),
    kind: Literal["overall", "style", "production"] = "overall",
    variant: Literal["any", "younger", "better"] = "any",
    db: Session = Depends(get_db),
):
    player = get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )
    return get_similar_players(db, player_id, season, limit, kind, variant)
