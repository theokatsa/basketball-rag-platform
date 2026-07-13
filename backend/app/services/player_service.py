from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player_schema import PlayerCreate


def get_all_players(db: Session):
    return db.query(Player).all()


def get_player_by_id(db: Session, player_id: int):
    return db.query(Player).filter(Player.id == player_id).first()


def create_player(db: Session, player_in: PlayerCreate):
    player = Player(
        nba_player_id=player_in.nba_player_id,
        full_name=player_in.full_name,
        first_name=player_in.first_name,
        last_name=player_in.last_name,
        is_active=player_in.is_active,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def get_player_season_stats(db: Session, player_id: int):
    sql = text(
        """
        select player_id,
               season,
               team_id,
               games_played,
               minutes,
               points,
               rebounds,
               assists,
               steals,
               blocks,
               turnovers,
               field_goal_pct,
               three_point_pct,
               free_throw_pct
        from player_season_stats
        where player_id = :player_id
        order by season desc
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()


def get_player_game_logs(db: Session, player_id: int):
    sql = text(
        """
        select pgl.player_id,
               pgl.game_id,
               pgl.season,
               pgl.minutes,
               pgl.points,
               pgl.rebounds,
               pgl.assists,
               pgl.steals,
               pgl.blocks,
               pgl.turnovers,
               pgl.field_goals_made,
               pgl.field_goals_attempted,
               pgl.three_pointers_made,
               pgl.three_pointers_attempted,
               pgl.free_throws_made,
               pgl.free_throws_attempted,
               pgl.plus_minus,
               g.nba_game_id,
               g.game_date::text as game_date
        from player_game_logs pgl
        left join games g on g.id = pgl.game_id
        where pgl.player_id = :player_id
        order by g.game_date desc nulls last
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()


def get_player_shots(db: Session, player_id: int):
    sql = text(
        """
        select player_id,
               nba_player_id,
               nba_game_id,
               season,
               team_id,
               period,
               minutes_remaining,
               seconds_remaining,
               event_type,
               action_type,
               shot_type,
               shot_zone_basic,
               shot_zone_area,
               shot_zone_range,
               shot_distance,
               loc_x,
               loc_y,
               shot_made,
               game_date::text as game_date,
               matchup
        from shot_charts
        where player_id = :player_id
        order by game_date desc nulls last
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()
