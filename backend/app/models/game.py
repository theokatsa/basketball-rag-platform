from sqlalchemy import Column, Date, DateTime, Integer, String, func

from app.db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    nba_game_id = Column(String, unique=True, index=True, nullable=False)
    season = Column(String, nullable=False)
    game_date = Column(Date, nullable=False)
    home_team_id = Column(Integer, nullable=True)
    away_team_id = Column(Integer, nullable=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)