from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), unique=True, nullable=False)
    season = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    position = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(String, nullable=True)
    weight = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)