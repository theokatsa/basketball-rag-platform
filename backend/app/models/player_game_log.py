from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class PlayerGameLog(Base):
    __tablename__ = "player_game_logs"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    season = Column(String, nullable=False)
    minutes = Column(Text, nullable=False)
    points = Column(Integer, nullable=False)
    rebounds = Column(Integer, nullable=False)
    assists = Column(Integer, nullable=False)
    steals = Column(Integer, nullable=False)
    blocks = Column(Integer, nullable=False)
    turnovers = Column(Integer, nullable=False)
    field_goals_made = Column(Integer, nullable=False)
    field_goals_attempted = Column(Integer, nullable=False)
    three_pointers_made = Column(Integer, nullable=False)
    three_pointers_attempted = Column(Integer, nullable=False)
    free_throws_made = Column(Integer, nullable=False)
    free_throws_attempted = Column(Integer, nullable=False)
    plus_minus = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)