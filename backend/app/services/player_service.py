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
               s.free_throw_pct * 100 as free_throw_pct,
               prof.position,
               prof.age
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
        left join player_profiles prof on prof.player_id = p.id
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
    """Every game from the complete box scores, with opponent and result."""
    sql = text(
        """
        select b.player_id, g.id as game_id, b.season, b.minutes::text as minutes, b.points,
               b.reb as rebounds, b.ast as assists, b.stl as steals, b.blk as blocks, b.tov as turnovers,
               b.fgm as field_goals_made, b.fga as field_goals_attempted,
               b.tpm as three_pointers_made, b.tpa as three_pointers_attempted,
               b.ftm as free_throws_made, b.fta as free_throws_attempted, b.plus_minus,
               b.oreb, b.dreb, b.pf, b.nba_game_id, b.game_date::text as game_date,
               o.abbreviation as opponent, t.is_home, t.won, t.points as team_points, t.opponent_points,
               t.opponent_nba_team_id as opponent_id
        from player_box_scores b
        join team_box_scores t on t.nba_game_id = b.nba_game_id and t.nba_team_id = b.nba_team_id
        join teams o on o.nba_team_id = t.opponent_nba_team_id
        left join games g on g.nba_game_id = b.nba_game_id
        where b.player_id = :player_id
        order by b.game_date desc
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()


def get_player_totals(db: Session):
    """Summed box scores and advanced rates per player for the most recent season."""
    sql = text(
        """
        with box as (
            select player_id, count(*) as games_played, sum(minutes)::int as minutes, sum(points) as points,
                   sum(reb) as rebounds, sum(ast) as assists, sum(stl) as steals, sum(blk) as blocks, sum(tov) as turnovers,
                   sum(fgm) as field_goals_made, sum(fga) as field_goals_attempted,
                   sum(tpm) as three_pointers_made, sum(tpa) as three_pointers_attempted,
                   sum(ftm) as free_throws_made, sum(fta) as free_throws_attempted,
                   sum(plus_minus)::int as plus_minus, sum(oreb) as oreb, sum(dreb) as dreb, sum(pf) as pf,
                   count(*) filter (where (points >= 10)::int + (reb >= 10)::int + (ast >= 10)::int + (stl >= 10)::int + (blk >= 10)::int >= 2) as double_doubles,
                   count(*) filter (where (points >= 10)::int + (reb >= 10)::int + (ast >= 10)::int + (stl >= 10)::int + (blk >= 10)::int >= 3) as triple_doubles
            from player_box_scores
            where season = (select max(season) from player_box_scores)
            group by player_id
        )
        select box.*, a.season_age, a.off_rating, a.def_rating, a.net_rating, a.ast_pct * 100 as ast_pct, a.ast_to,
               a.oreb_pct * 100 as oreb_pct, a.dreb_pct * 100 as dreb_pct, a.efg_pct * 100 as efg_pct, a.usg_pct * 100 as usg_pct,
               a.pace, a.pie * 100 as pie, a.defended_fga, a.defended_fg_pct * 100 as defended_fg_pct, a.defended_fg_diff * 100 as defended_fg_diff
        from box
        left join player_advanced_stats a on a.player_id = box.player_id and a.season = (select max(season) from player_box_scores)
        """
    )
    return db.execute(sql).mappings().all()


def get_player_shot_zones(db: Session):
    """Attempts and makes per player and court zone, for the latest season."""
    sql = text(
        """
        select player_id, shot_zone_basic, shot_zone_area,
               count(*) as attempts, sum(shot_made::int) as made
        from shot_charts
        where season = (select max(season) from shot_charts) and player_id is not null
        group by player_id, shot_zone_basic, shot_zone_area
        """
    )
    return db.execute(sql).mappings().all()


def get_team_shot_zones(db: Session):
    sql = text(
        """
        select t.nba_team_id as team_id, sc.shot_zone_basic, sc.shot_zone_area,
               count(*) as attempts, sum(sc.shot_made::int) as made
        from shot_charts sc
        join teams t on t.id = sc.team_id
        where sc.season = (select max(season) from shot_charts)
        group by t.nba_team_id, sc.shot_zone_basic, sc.shot_zone_area
        """
    )
    return db.execute(sql).mappings().all()


def get_player_form(db: Session, games: int):
    """Average over each player's last N games against their earlier games."""
    sql = text(
        """
        with ordered as (
            select pgl.*, row_number() over (partition by pgl.player_id order by g.game_date desc) as n,
                   split_part(pgl.minutes, ':', 1)::numeric as mins
            from player_game_logs pgl
            join games g on g.id = pgl.game_id
            where pgl.season = (select max(season) from player_game_logs)
        )
        select player_id,
               count(*) as games_played,
               avg(points) filter (where n <= :n)::float as recent_points,
               avg(rebounds) filter (where n <= :n)::float as recent_rebounds,
               avg(assists) filter (where n <= :n)::float as recent_assists,
               avg(mins) filter (where n <= :n)::float as recent_minutes,
               avg(points) filter (where n > :n)::float as earlier_points,
               avg(rebounds) filter (where n > :n)::float as earlier_rebounds,
               avg(assists) filter (where n > :n)::float as earlier_assists,
               avg(mins) filter (where n > :n)::float as earlier_minutes,
               (array_agg(points order by n desc) filter (where n <= :n)) as recent_games
        from ordered
        group by player_id
        having count(*) >= :n * 2
        """
    )
    return db.execute(sql, {"n": games}).mappings().all()


def get_league_shot_zones(db: Session):
    sql = text(
        """
        select shot_zone_basic, shot_zone_area,
               count(*) as attempts,
               sum(shot_made::int) as made
        from shot_charts
        group by shot_zone_basic, shot_zone_area
        """
    )
    return db.execute(sql).mappings().all()


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
