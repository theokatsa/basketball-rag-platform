from pydantic import BaseModel


class PlayerDirectoryRowResponse(BaseModel):
    player_id: int
    nba_player_id: int
    full_name: str
    is_active: bool
    season: str | None
    club: str | None
    club_full_name: str | None
    club_team_id: int | None
    games_played: int | None
    minutes: float | None
    points: float | None
    rebounds: float | None
    assists: float | None
    steals: float | None
    blocks: float | None
    turnovers: float | None
    field_goal_pct: float | None
    three_point_pct: float | None
    free_throw_pct: float | None
    position: str | None = None
    age: int | None = None
