from pydantic import BaseModel, ConfigDict


class PlayerCreate(BaseModel):
    nba_player_id: int
    full_name: str
    first_name: str
    last_name: str
    is_active: bool = True


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nba_player_id: int
    full_name: str
    first_name: str
    last_name: str
    is_active: bool
