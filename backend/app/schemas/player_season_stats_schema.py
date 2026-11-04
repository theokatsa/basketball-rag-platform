from pydantic import BaseModel


class PlayerSeasonStatsResponse(BaseModel):
    player_id: int
    season: str
    team_id: int | None
    position: str | None = None
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
    points_percentile: float | None = None
    rebounds_percentile: float | None = None
    assists_percentile: float | None = None
    steals_percentile: float | None = None
    blocks_percentile: float | None = None
    field_goal_percentile: float | None = None
    position_points_percentile: float | None = None
    position_rebounds_percentile: float | None = None
    position_assists_percentile: float | None = None
    position_steals_percentile: float | None = None
    position_blocks_percentile: float | None = None
    position_field_goal_percentile: float | None = None
    points_rank: int | None = None
    rebounds_rank: int | None = None
    assists_rank: int | None = None
    steals_rank: int | None = None
    blocks_rank: int | None = None
    turnovers_rank: int | None = None
    field_goal_rank: int | None = None
    three_point_rank: int | None = None
    free_throw_rank: int | None = None
