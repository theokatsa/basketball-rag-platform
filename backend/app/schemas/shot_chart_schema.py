from pydantic import BaseModel


class ShotChartResponse(BaseModel):
    player_id: int
    nba_player_id: int
    nba_game_id: str
    season: str
    team_id: int | None
    period: int
    minutes_remaining: int
    seconds_remaining: int
    event_type: str
    action_type: str
    shot_type: str
    shot_zone_basic: str
    shot_zone_area: str
    shot_zone_range: str
    shot_distance: int
    loc_x: int
    loc_y: int
    shot_made: bool
    game_date: str | None
    matchup: str
