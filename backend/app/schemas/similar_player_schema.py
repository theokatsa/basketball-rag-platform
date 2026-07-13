from pydantic import BaseModel, ConfigDict


class SimilarPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    full_name: str
    season: str
    source_text: str
    similarity: float