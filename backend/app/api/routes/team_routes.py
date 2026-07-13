from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.team_schema import TeamResponse
from app.services.team_service import get_all_teams, get_team_by_id

router = APIRouter()


@router.get("/teams", response_model=list[TeamResponse])
def read_teams(db: Session = Depends(get_db)):
    return get_all_teams(db)


@router.get("/teams/{team_id}", response_model=TeamResponse)
def read_team(team_id: int, db: Session = Depends(get_db)):
    team = get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team
