from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: int
    nba_team_id: int
    abbreviation: str
    full_name: str
    city: str
    nickname: str
    state: str
    year_founded: int
