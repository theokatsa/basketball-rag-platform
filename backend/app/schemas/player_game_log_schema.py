from pydantic import BaseModel


class PlayerGameLogResponse(BaseModel):
    player_id: int
    game_id: int | None
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
    oreb: int
    dreb: int
    pf: int
    won: bool
    team_points: int
    opponent_points: int
    opponent_id: int


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
    oreb: int
    dreb: int
    pf: int
    double_doubles: int
    triple_doubles: int
    season_age: int | None = None
    off_rating: float | None = None
    def_rating: float | None = None
    net_rating: float | None = None
    ast_pct: float | None = None
    ast_to: float | None = None
    oreb_pct: float | None = None
    dreb_pct: float | None = None
    efg_pct: float | None = None
    usg_pct: float | None = None
    pace: float | None = None
    pie: float | None = None
    defended_fga: float | None = None
    defended_fg_pct: float | None = None
    defended_fg_diff: float | None = None


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
    game_id: str
    game_date: str | None
    team_id: int
    opponent_id: int
    opponent: str
    is_home: bool
    won: bool
    team_points: int
    opponent_points: int
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    field_goals_made: int
    field_goals_attempted: int
    game_score: float
