from pydantic import BaseModel


class TopScorerResponse(BaseModel):
    player_id: int
    full_name: str
    team_id: int | None
    season: str
    games_played: int
    points: float


class TopAssisterResponse(BaseModel):
    player_id: int
    full_name: str
    team_id: int | None
    season: str
    games_played: int
    assists: float


class PlayerComparisonItem(BaseModel):
    player_id: int
    full_name: str
    season: str
    team_id: int | None
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float


class ShotProfileResponse(BaseModel):
    shot_zone_basic: str
    shot_zone_area: str
    shot_zone_range: str
    attempts: int
    made: int
    pct: float | None
