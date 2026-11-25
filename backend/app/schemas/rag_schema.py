from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    season: str | None = None
    limit: int = Field(default=6, ge=1, le=12)
    previous: str | None = Field(default=None, max_length=1000)  # the question before, for follow-ups


class RagSource(BaseModel):
    ref: int
    kind: str
    title: str
    player_id: int | None = None
    full_name: str
    season: str
    source_text: str
    similarity: float | None = None


class AnswerChecks(BaseModel):
    numbers: int
    unsupported_numbers: list[str]
    cited: list[int]
    invalid_citations: list[int]
    grounded: bool


class AskResponse(BaseModel):
    answer: str
    provider: str
    understood: str = ""  # the question as it was answered, after resolving "he" or "what about"
    model: str
    sources: list[RagSource]
    plan: list[str] = []
    intent: str = ""
    options: list[str] = []  # questions to choose from when this one was unclear
    table: dict | None = None  # calculated answers: {"columns": [...], "rows": [[...]]}
    checks: AnswerChecks | None = None
    retrieval_ms: int = 0
    generation_ms: int = 0
