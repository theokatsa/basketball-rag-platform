from pydantic import BaseModel, ConfigDict, Field, model_validator


class SimilarPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    full_name: str
    season: str
    source_text: str
    similarity: float
    age: int | None = None
    position: str | None = None
    is_active: bool


class SimilarPlayerSearchRequest(BaseModel):
    player_id: int | None = None
    player_name: str | None = None
    season: str | None = None
    limit: int = Field(default=5, ge=1, le=50)
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)
    position: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_reference_player(self):
        if self.player_id is None and not self.player_name:
            raise ValueError("Provide either player_id or player_name")

        if (
            self.min_age is not None
            and self.max_age is not None
            and self.min_age > self.max_age
        ):
            raise ValueError("min_age cannot be greater than max_age")

        return self


class SimilarPlayerReferenceOptionResponse(BaseModel):
    player_id: int
    full_name: str


class SimilarPlayerPositionOptionResponse(BaseModel):
    position: str