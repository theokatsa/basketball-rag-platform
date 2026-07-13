from sqlalchemy import Column, DateTime, Integer, String, func

from app.db import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    nba_team_id = Column(Integer, unique=True, index=True, nullable=False)
    abbreviation = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    nickname = Column(String, nullable=False)
    state = Column(String, nullable=False)
    year_founded = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
