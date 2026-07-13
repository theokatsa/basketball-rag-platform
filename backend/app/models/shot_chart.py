from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, func

from app.db import Base


class ShotChart(Base):
    __tablename__ = "shot_charts"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    nba_player_id = Column(Integer, nullable=False)
    nba_game_id = Column(String, nullable=False)
    season = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    period = Column(Integer, nullable=False)
    minutes_remaining = Column(Integer, nullable=False)
    seconds_remaining = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    shot_type = Column(String, nullable=False)
    shot_zone_basic = Column(String, nullable=False)
    shot_zone_area = Column(String, nullable=False)
    shot_zone_range = Column(String, nullable=False)
    shot_distance = Column(Integer, nullable=False)
    loc_x = Column(Integer, nullable=False)
    loc_y = Column(Integer, nullable=False)
    shot_made = Column(Boolean, nullable=False)
    game_date = Column(Date, nullable=True)
    matchup = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)