from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    season: str | None = None
    limit: int = Field(default=6, ge=1, le=12)


class RagSource(BaseModel):
    player_id: int
    full_name: str
    season: str
    source_text: str
    similarity: float


class AskResponse(BaseModel):
    answer: str
    provider: str
    model: str
    sources: list[RagSource]
