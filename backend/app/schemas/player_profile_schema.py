from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlayerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: int
    season: str
    team_id: int | None
    position: str | None
    age: int | None
    height: str | None
    weight: str | None
    description: str | None
    created_at: datetime | None = None