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
