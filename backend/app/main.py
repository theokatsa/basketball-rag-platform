from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.analytics_routes import router as analytics_router
from app.api.routes.player_routes import router as player_router
from app.api.routes.search_routes import router as search_router
from app.api.routes.team_routes import router as team_router
from app.db import engine

app = FastAPI(title="Basketball Analytics API")

app.include_router(player_router, tags=["players"])
app.include_router(team_router, tags=["teams"])
app.include_router(analytics_router, tags=["analytics"])
app.include_router(search_router, tags=["search"])


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def startup_check_db():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
