import logging
from threading import Thread

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.player_routes import router as player_router
from app.api.routes.search_routes import router as search_router
from app.api.routes.rag_routes import router as rag_router
from app.api.routes.game_routes import router as game_router
from app.api.routes.user_routes import router as user_router
from app.api.routes.chat_routes import router as chat_router
from app.db import SessionLocal, engine
from app.services import feedback_service
from app.services.league_data import warm
from app.services.query_embedding_service import warm_up

app = FastAPI(title="Basketball Analytics API")

app.include_router(player_router, tags=["players"])
app.include_router(search_router, tags=["search"])
app.include_router(rag_router, tags=["rag"])
app.include_router(game_router, tags=["games"])
app.include_router(user_router, tags=["users"])
app.include_router(chat_router, tags=["chats"])


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def startup_check_db():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def prepare():
    try:
        feedback_service.ensure_schema(engine)  # the question log is new; create if not exists
    except Exception as error:  # noqa: BLE001 - answering works without the log
        logging.getLogger(__name__).warning("question log unavailable: %s", error)
    warm_up()
    with SessionLocal() as db:
        warm(db)


@app.on_event("startup")
def load_in_background():
    # The embedding model and the season tables take up to a minute; the API answers meanwhile.
    Thread(target=prepare, daemon=True).start()
