from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlayerEmbeddingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: int
    season: str
    source_text: str
    created_at: datetime | None = None