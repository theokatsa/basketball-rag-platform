from pydantic import BaseModel, ConfigDict


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nba_team_id: int
    abbreviation: str
    full_name: str
    city: str
    nickname: str
    state: str
    year_founded: int
