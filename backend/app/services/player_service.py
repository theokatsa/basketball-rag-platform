from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player_schema import PlayerCreate


def get_all_players(db: Session):
    return db.query(Player).all()


def get_players_directory(db: Session, season: str | None = None):
    sql = text(
        """
         select p.id as player_id,
             p.nba_player_id,
               p.full_name,
               p.is_active,
               s.season,
               t.abbreviation as club,
               t.full_name as club_full_name,
               t.nba_team_id as club_team_id,
               s.games_played,
               s.minutes,
               s.points,
               s.rebounds,
               s.assists,
               s.steals,
               s.blocks,
               s.turnovers,
               s.field_goal_pct * 100 as field_goal_pct,
               s.three_point_pct * 100 as three_point_pct,
               s.free_throw_pct * 100 as free_throw_pct
        from players p
        left join lateral (
             select ps.player_id,
                 ps.season,
                   ps.team_id,
                   ps.games_played,
                 ps.minutes,
                   ps.points,
                   ps.rebounds,
                 ps.assists,
                 ps.steals,
                 ps.blocks,
                 ps.turnovers,
                 ps.field_goal_pct,
                 ps.three_point_pct,
                 ps.free_throw_pct
            from player_season_stats ps
            where ps.player_id = p.id
              and (:season is null or ps.season = :season)
            order by ps.season desc
            limit 1
        ) s on true
        left join teams t on t.id = s.team_id
        where s.player_id is not null
        order by p.full_name
        """
    )
    return db.execute(sql, {"season": season}).mappings().all()


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
        with ranked_stats as (
            select ps.*,
                   profile.position,
                   percent_rank() over (partition by ps.season order by ps.points desc) as points_percentile,
                   percent_rank() over (partition by ps.season order by ps.rebounds desc) as rebounds_percentile,
                   percent_rank() over (partition by ps.season order by ps.assists desc) as assists_percentile,
                   percent_rank() over (partition by ps.season order by ps.steals desc) as steals_percentile,
                   percent_rank() over (partition by ps.season order by ps.blocks desc) as blocks_percentile,
                   percent_rank() over (partition by ps.season order by ps.field_goal_pct desc) as field_goal_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.points desc) as position_points_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.rebounds desc) as position_rebounds_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.assists desc) as position_assists_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.steals desc) as position_steals_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.blocks desc) as position_blocks_percentile,
                   percent_rank() over (partition by ps.season, profile.position order by ps.field_goal_pct desc) as position_field_goal_percentile,
                   rank() over (partition by ps.season order by ps.points desc) as points_rank,
                   rank() over (partition by ps.season order by ps.rebounds desc) as rebounds_rank,
                   rank() over (partition by ps.season order by ps.assists desc) as assists_rank,
                   rank() over (partition by ps.season order by ps.steals desc) as steals_rank,
                   rank() over (partition by ps.season order by ps.blocks desc) as blocks_rank,
                   rank() over (partition by ps.season order by ps.turnovers) as turnovers_rank,
                   rank() over (partition by ps.season order by ps.field_goal_pct desc) as field_goal_rank,
                   rank() over (partition by ps.season order by ps.three_point_pct desc) as three_point_rank,
                   rank() over (partition by ps.season order by ps.free_throw_pct desc) as free_throw_rank
            from player_season_stats ps
            left join player_profiles profile on profile.player_id = ps.player_id
        )
        select *
        from ranked_stats
        where player_id = :player_id
        order by season desc
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()


def get_player_profile(db: Session, player_id: int):
    sql = text(
        """
        select id, player_id, season, team_id, position, age, height, weight, description, created_at
        from player_profiles
        where player_id = :player_id
        order by season desc
        limit 1
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().first()


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
