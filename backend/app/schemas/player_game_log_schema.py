from pydantic import BaseModel


class PlayerGameLogResponse(BaseModel):
    player_id: int
    game_id: int
    season: str
    minutes: str
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    field_goals_made: int
    field_goals_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    plus_minus: int | None
    nba_game_id: str | None
    game_date: str | None
    opponent: str | None = None
    is_home: bool | None = None


class PlayerTotalsResponse(BaseModel):
    player_id: int
    games_played: int
    minutes: int
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    field_goals_made: int
    field_goals_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    plus_minus: int


class LeagueShotZoneResponse(BaseModel):
    shot_zone_basic: str
    shot_zone_area: str
    attempts: int
    made: int


class PlayerShotZoneResponse(LeagueShotZoneResponse):
    player_id: int


class TeamShotZoneResponse(LeagueShotZoneResponse):
    team_id: int


class PlayerFormResponse(BaseModel):
    player_id: int
    games_played: int
    recent_points: float
    recent_rebounds: float
    recent_assists: float
    recent_minutes: float
    earlier_points: float
    earlier_rebounds: float
    earlier_assists: float
    earlier_minutes: float
    recent_games: list[int]


class BestGameResponse(BaseModel):
    player_id: int
    game_date: str | None
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    field_goals_made: int
    field_goals_attempted: int
    game_score: float
    opponent: str | None
    is_home: bool | None
