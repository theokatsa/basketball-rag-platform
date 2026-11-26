import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.user_routes import current_user
from app.db import SessionLocal, get_db
from app.schemas.rag_schema import UUID, AnswerFeedback, AskRequest, AskResponse, SimilarFeedback
from app.services import chat_service, feedback_service, rag_service
from app.services.evaluation_summary import summary
from app.services.llm_service import LLMError
from app.services.metrics import PLAYER_METRICS, TEAM_METRICS
from app.services.rag_service import answer_question
from app.services.retrieval import retrieve

router = APIRouter()


def _keep_turn(user_id: int | None, visitor: str | None, chat_id: str, question: str, result: dict) -> None:
    """Runs after the answer was sent, with its own connection."""
    try:
        with SessionLocal() as db:
            chat_service.append(db, user_id, visitor, chat_id, question, result)
    except Exception as error:  # noqa: BLE001 - a lost turn must not break answering
        logging.getLogger(__name__).warning("chat turn not kept: %s", error)


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, background: BackgroundTasks, db: Session = Depends(get_db), user=Depends(current_user)):
    user_id = user["id"] if user else None
    earlier = chat_service.history(db, user_id, payload.visitor, payload.chat_id) if payload.chat_id and (user_id or payload.visitor) else []
    previous = payload.previous if payload.previous is not None else (earlier[-1] if earlier else None)
    try:
        result = answer_question(db, payload.question, payload.season, payload.limit, previous, payload.query, payload.reader, history=earlier)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve basketball evidence from the database.",
        ) from exc
    if payload.log:
        # Written after the response is sent, so keeping the question costs the person no time.
        result["ask_id"] = feedback_service.new_id()
        background.add_task(feedback_service.log_question, result["ask_id"], payload.visitor, payload.question, previous, result)
    if payload.chat_id and (user_id or payload.visitor):
        background.add_task(_keep_turn, user_id, payload.visitor, payload.chat_id, payload.question, dict(result))
    return result


class CompareRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/ask/compare")
def compare(payload: CompareRequest, db: Session = Depends(get_db)):
    """One question, every way of answering it: the two readers, and the four ways of retrieving documents."""
    try:
        with rag_service.without_writing():
            readers = {"rules": rag_service.answer_question(db, payload.question, None, 6, reader="rules")}
            if rag_service.default_reader() == "llm":
                readers["llm"] = rag_service.answer_question(db, payload.question, None, 6, reader="llm")
        methods = {}
        for mode in ("keyword", "vector", "hybrid", "planned"):
            rows, _ = retrieve(db, payload.question, None, 6, mode)
            methods[mode] = [{"title": r["title"], "kind": r["kind"]} for r in rows]
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Unable to reach the database.") from exc
    keep = ("answer", "provider", "reader", "understood", "plan", "query", "confidence", "reader_note", "reader_model")
    return {"readers": {k: {f: v.get(f) for f in keep} for k, v in readers.items()}, "methods": methods}


class Judgment(BaseModel):
    trial: str = Field(pattern=UUID)
    visitor: str = Field(pattern=UUID)
    choice: Literal["left", "right", "same"]


@router.get("/judge/next")
def judge_next(visitor: str = Query(pattern=UUID), db: Session = Depends(get_db)):
    """A player and two lists of similar players from two methods, in random order; null when all are judged."""
    return feedback_service.next_trial(db, visitor)


@router.post("/judge", status_code=204)
def judge(payload: Judgment, request: Request, db: Session = Depends(get_db)):
    if not feedback_service.allowed(_client(request)):
        raise HTTPException(429, "Too many answers at once. Please wait a few minutes.")
    if not feedback_service.save_judgment(db, payload.trial, payload.visitor, payload.choice):
        raise HTTPException(410, "This pair expired. A new one is on its way.")


@router.get("/evaluation/summary")
def evaluation_summary():
    return summary()


@router.get("/ask/catalog")
def catalog():
    """The statistics a StatQuery can use, for the chips that edit one."""
    return {"player": [[m.key, m.label] for m in PLAYER_METRICS], "team": [[m.key, m.label] for m in TEAM_METRICS]}


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post("/feedback/answer", status_code=204)
def feedback_on_answer(payload: AnswerFeedback, request: Request, db: Session = Depends(get_db)):
    if not feedback_service.allowed(_client(request)):
        raise HTTPException(429, "Too much feedback at once. Please wait a few minutes.")
    if not feedback_service.answer_feedback(db, payload.ask_id, payload.helpful, payload.reason, payload.comment):
        raise HTTPException(404, "This answer was not kept, so feedback on it cannot be saved.")


@router.post("/feedback/similar", status_code=204)
def feedback_on_similar(payload: SimilarFeedback, request: Request, db: Session = Depends(get_db)):
    if not feedback_service.allowed(_client(request)):
        raise HTTPException(429, "Too much feedback at once. Please wait a few minutes.")
    if payload.player_id == payload.other_id:
        raise HTTPException(422, "A player cannot be similar to himself.")
    try:
        feedback_service.similar_feedback(db, payload.visitor, payload.player_id, payload.other_id, payload.kind, payload.variant, payload.rank, payload.similarity, payload.good)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(404, "Unknown player.") from exc
