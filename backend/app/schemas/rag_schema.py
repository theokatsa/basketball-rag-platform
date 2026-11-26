from typing import Literal

from pydantic import BaseModel, Field

UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    season: str | None = None
    limit: int = Field(default=6, ge=1, le=12)
    previous: str | None = Field(default=None, max_length=1000)  # the question before, for follow-ups
    log: bool = True  # false: the person asked not to keep their questions
    query: dict | None = None  # a StatQuery edited on the page: calculated as it is, without reading the question again
    reader: Literal["llm", "rules"] | None = None  # None: the default (the language model when a key is set)
    chat_id: str | None = Field(default=None, pattern=UUID)  # the conversation this question belongs to: kept, and read for follow-ups
    visitor: str | None = Field(default=None, pattern=UUID)  # a random number kept by the browser, not a person


class AnswerFeedback(BaseModel):
    ask_id: str = Field(pattern=UUID)
    helpful: bool
    reason: Literal["wrong_stat", "wrong_player", "should_decline", "wrong_number", "other"] | None = None
    comment: str | None = Field(default=None, max_length=600)


class SimilarFeedback(BaseModel):
    visitor: str = Field(pattern=UUID)
    player_id: int
    other_id: int
    kind: Literal["overall", "style", "production"]
    variant: Literal["any", "younger", "better"] = "any"
    rank: int = Field(ge=1, le=50)
    similarity: float | None = None
    good: bool


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
    misattributed: list[str] = []  # numbers the sources give to another player or team
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
    ask_id: str | None = None  # where feedback on this answer goes; None when it was not logged
    model_error: str | None = None  # the language model failed, so the answer was made without it
    reader: str = "rules"  # who read the question: llm, rules, or edited (a person changed the query)
    query: dict | None = None  # the StatQuery behind the answer, for the editable chips
    reader_note: str = ""  # why the rule reader answered instead of the language model
    reader_model: str = ""
    reader_ms: int = 0
    reader_tokens: int = 0
    generation_tokens: int = 0
    confidence: float = 0.0  # 0-1, how sure the system is; 0 when it declined or asked back
    signals: dict = {}  # what the confidence was made from
