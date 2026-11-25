import time
from collections import defaultdict, deque

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import COOKIE_SECURE
from app.db import get_db
from app.services import user_service

router = APIRouter()
COOKIE = "scouting_session"
MAX_ATTEMPTS, WINDOW = 10, 900
_attempts: dict[str, deque] = defaultdict(deque)


def throttle(key: str):
    """At most 10 tries per 15 minutes per key."""
    now = time.monotonic()
    if len(_attempts) > 5000:
        for old in [k for k, v in list(_attempts.items()) if not v or now - v[-1] > WINDOW]:
            _attempts.pop(old, None)
    recent = _attempts[key]
    while recent and now - recent[0] > WINDOW:
        recent.popleft()
    if len(recent) >= MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Please wait a few minutes.")
    recent.append(now)


def current_user(scouting_session: str | None = Cookie(None), db: Session = Depends(get_db)):
    return user_service.user_for(db, scouting_session)


def required_user(user=Depends(current_user)):
    if user is None:
        raise HTTPException(401, "Please sign in.")
    return user


class Password(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class Credentials(Password):
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email", mode="before")
    @classmethod
    def tidy(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class Signup(Credentials):
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=40)

    @field_validator("display_name", mode="before")
    @classmethod
    def tidy_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ScoutNote(BaseModel):
    text: str = Field(default="", max_length=600)
    stars: int = Field(default=0, ge=0, le=5)
    status: str = Field(default="", max_length=20)


class State(BaseModel):
    favorites: list[int] = Field(default=[], max_length=600)
    groups: dict[str, list[int]] = {}
    history: list[int] = Field(default=[], max_length=50)
    notes: dict[int, ScoutNote] = Field(default={}, max_length=600)

    @field_validator("groups")
    @classmethod
    def limited(cls, value):
        if len(value) > 50 or any(len(k) > 60 or len(v) > 600 for k, v in value.items()):
            raise ValueError("Too many groups")
        return value


def sign_in(response: Response, db: Session, user: dict):
    token = user_service.start_session(db, user["id"])
    response.set_cookie(COOKIE, token, max_age=user_service.SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")


def public(user: dict):
    return {"id": user["id"], "email": user["email"], "display_name": user["display_name"], "created_at": str(user["created_at"])}


@router.post("/auth/signup", status_code=201)
def signup(payload: Signup, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(f"signup:{request.client.host if request.client else ''}")
    user = user_service.create_user(db, payload.email, payload.display_name, payload.password)
    if user is None:
        raise HTTPException(409, "An account with this email already exists.")
    sign_in(response, db, user)
    return public(user)


@router.post("/auth/login")
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    throttle(f"login:{payload.email}")
    user = user_service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Wrong email or password.")
    _attempts.pop(f"login:{payload.email}", None)
    sign_in(response, db, user)
    return public(user)


@router.post("/auth/logout", status_code=204)
def logout(response: Response, scouting_session: str | None = Cookie(None), db: Session = Depends(get_db)):
    if scouting_session:
        user_service.end_session(db, scouting_session)
    response.delete_cookie(COOKIE, path="/")


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return {"user": public(user) if user else None, "state": user["state"] if user else None}


@router.put("/me/state", status_code=204)
def put_state(payload: State, user=Depends(required_user), db: Session = Depends(get_db)):
    user_service.save_state(db, user["id"], payload.model_dump())


@router.post("/me/views/{player_id}", status_code=204)
def add_view(player_id: int, user=Depends(required_user), db: Session = Depends(get_db)):
    user_service.record_view(db, user["id"], player_id)


@router.get("/me/activity")
def my_activity(user=Depends(required_user), db: Session = Depends(get_db)):
    return user_service.activity(db, user["id"])


@router.delete("/me/activity", status_code=204)
def forget_activity(user=Depends(required_user), db: Session = Depends(get_db)):
    user_service.clear_activity(db, user["id"])


@router.post("/me/delete", status_code=204)
def remove_account(payload: Password, response: Response, user=Depends(required_user), db: Session = Depends(get_db)):
    throttle(f"login:{user['email']}")
    if not user_service.authenticate(db, user["email"], payload.password):
        raise HTTPException(403, "Wrong password.")
    user_service.delete_user(db, user["id"])
    response.delete_cookie(COOKIE, path="/")


@router.get("/players/{player_id}/also-viewed")
def players_also_viewed(player_id: int, limit: int = Query(6, ge=1, le=12), db: Session = Depends(get_db)):
    return user_service.also_viewed(db, player_id, limit)
