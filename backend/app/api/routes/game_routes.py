from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import recommend_service, team_style
from app.services import form_service, game_service, insight_service, shot_service

router = APIRouter()


@router.get("/games")
def read_games(db: Session = Depends(get_db)):
    return game_service.list_games(db)


@router.get("/games/{game_id}")
def read_game(game_id: str, db: Session = Depends(get_db)):
    game = game_service.get_game(db, game_id)
    if game is None:
        raise HTTPException(404, "Game not found")
    return game


@router.get("/team-summaries")
def read_team_summaries(db: Session = Depends(get_db)):
    return game_service.team_summaries(db)


@router.get("/shots/zones")
def read_zones(opponent: str | None = Query(None, pattern="^[A-Z]{3}$"), db: Session = Depends(get_db)):
    return shot_service.player_zones(db, opponent)


@router.get("/shots/league-zones")
def read_league_zones(db: Session = Depends(get_db)):
    return shot_service.league_zones(db)


@router.get("/shots/team-zones")
def read_team_zones(side: str = Query("offense", pattern="^(offense|defense)$"), db: Session = Depends(get_db)):
    return shot_service.team_zones(db, side)


@router.get("/form")
def read_form(games: int = Query(10, ge=5, le=20), db: Session = Depends(get_db)):
    return form_service.form(db, games)


@router.get("/insights/players/{player_id}/fit")
def read_fit(player_id: int, db: Session = Depends(get_db)):
    fit = insight_service.player_fit(db, player_id)
    if fit is None:
        raise HTTPException(404, "No statistics for this player")
    return fit


@router.get("/insights/players/{player_id}/defenders")
def read_defenders(player_id: int, db: Session = Depends(get_db)):
    return insight_service.defenders(db, player_id)


@router.get("/insights/head-to-head")
def read_head_to_head(ids: str = Query(pattern=r"^\d+(,\d+){1,5}$"), db: Session = Depends(get_db)):
    return insight_service.head_to_head(db, [int(i) for i in ids.split(",")])


@router.get("/insights/scores")
def read_scores(db: Session = Depends(get_db)):
    return [{"player_id": p["player_id"], "score": p["score"], "offense": p["offense_score"], "defense": p["defense_score"]} for p in insight_service.load_profiles(db).values()]


@router.get("/insights/teams/{team_id}/targets")
def read_team_targets(team_id: int, limit: int = Query(8, ge=1, le=20), max_age: int | None = Query(None, ge=18, le=50), position: str | None = Query(None, pattern="^(Guard|Forward|Center)$"), db: Session = Depends(get_db)):
    targets = recommend_service.team_targets(db, team_id, limit, max_age, position)
    if targets is None:
        raise HTTPException(404, "No statistics for this team")
    return targets


@router.get("/insights/teams/{team_id}/similar")
def read_similar_teams(team_id: int, limit: int = Query(5, ge=1, le=10), db: Session = Depends(get_db)):
    teams = team_style.similar_teams(db, team_id, limit)
    if teams is None:
        raise HTTPException(404, "No statistics for this team")
    return teams


class SuggestionRequest(BaseModel):
    favorites: list[int] = Field(default=[], max_length=200)
    compared: list[int] = Field(default=[], max_length=20)
    viewed: list[int] = Field(default=[], max_length=50)  # newest first
    limit: int = Field(8, ge=1, le=24)
    max_age: int | None = Field(None, ge=18, le=50)
    position: str | None = Field(None, pattern="^(Guard|Forward|Center)$")


@router.post("/suggestions")
def read_suggestions(payload: SuggestionRequest, db: Session = Depends(get_db)):
    return recommend_service.suggest(db, payload.favorites, payload.compared, payload.viewed, payload.limit, payload.max_age, payload.position)


class LineupRequest(BaseModel):
    player_ids: list[int] = Field(min_length=5, max_length=5)


@router.post("/insights/lineup")
def read_lineup(payload: LineupRequest, db: Session = Depends(get_db)):
    result = insight_service.analyze_lineup(db, payload.player_ids)
    if result is None:
        raise HTTPException(422, "Pick five different players with statistics this season.")
    return result
