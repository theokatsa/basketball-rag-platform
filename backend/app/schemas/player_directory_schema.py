from pydantic import BaseModel


class PlayerDirectoryRowResponse(BaseModel):
    player_id: int
    full_name: str
    is_active: bool
    season: str | None
    club: str | None
    games_played: int | None
    points: float | None
    rebounds: float | None
    assists: float | None
