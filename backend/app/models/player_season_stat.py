from sqlalchemy import Column, DateTime, ForeignKey, Float, Integer, String, func

from app.db import Base


class PlayerSeasonStat(Base):
    __tablename__ = "player_season_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    games_played = Column(Integer, nullable=False)
    minutes = Column(Float, nullable=False)
    points = Column(Float, nullable=False)
    rebounds = Column(Float, nullable=False)
    assists = Column(Float, nullable=False)
    steals = Column(Float, nullable=False)
    blocks = Column(Float, nullable=False)
    turnovers = Column(Float, nullable=False)
    field_goal_pct = Column(Float, nullable=True)
    three_point_pct = Column(Float, nullable=True)
    free_throw_pct = Column(Float, nullable=True)
    usage_rate = Column(Float, nullable=True)
    true_shooting_pct = Column(Float, nullable=True)
    player_efficiency_rating = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)