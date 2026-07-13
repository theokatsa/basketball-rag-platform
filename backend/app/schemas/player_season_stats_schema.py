from pydantic import BaseModel


class PlayerSeasonStatsResponse(BaseModel):
    player_id: int
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
    field_goal_pct: float | None
    three_point_pct: float | None
    free_throw_pct: float | None
