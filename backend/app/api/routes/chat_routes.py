import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.user_routes import current_user
from app.db import get_db
from app.schemas.rag_schema import UUID
from app.services import chat_service

router = APIRouter()


def _owner(user, visitor: str | None) -> tuple[int | None, str | None]:
    if user is None and not visitor:
        raise HTTPException(400, "Sign in, or let the page keep a random number for this browser.")
    return (user["id"] if user else None), visitor


@router.get("/chats")
def chats(visitor: str | None = Query(None, pattern=UUID), user=Depends(current_user), db: Session = Depends(get_db)):
    """Your conversations, newest first."""
    return chat_service.list_chats(db, *_owner(user, visitor))


@router.get("/chats/{chat_id}")
def chat(chat_id: str, visitor: str | None = Query(None, pattern=UUID), user=Depends(current_user), db: Session = Depends(get_db)):
    if not re.fullmatch(UUID, chat_id):
        raise HTTPException(404, "No such conversation.")
    turns = chat_service.get_chat(db, *_owner(user, visitor), chat_id)
    if turns is None:
        raise HTTPException(404, "No such conversation.")
    return turns


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, visitor: str | None = Query(None, pattern=UUID), user=Depends(current_user), db: Session = Depends(get_db)):
    if not re.fullmatch(UUID, chat_id) or not chat_service.delete_chat(db, *_owner(user, visitor), chat_id):
        raise HTTPException(404, "No such conversation.")
