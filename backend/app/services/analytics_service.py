from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def get_top_scorers(db: Session, season: str, limit: int):
    sql = text(
        """
        select p.id as player_id,
               p.full_name,
               s.team_id,
               s.season,
               s.games_played,
               s.points
        from player_season_stats s
        join players p on p.id = s.player_id
        where s.season = :season
        order by s.points desc
        limit :limit
        """
    )
    return db.execute(sql, {"season": season, "limit": limit}).mappings().all()


def get_top_assisters(db: Session, season: str, limit: int):
    sql = text(
        """
        select p.id as player_id,
               p.full_name,
               s.team_id,
               s.season,
               s.games_played,
               s.assists
        from player_season_stats s
        join players p on p.id = s.player_id
        where s.season = :season
        order by s.assists desc
        limit :limit
        """
    )
    return db.execute(sql, {"season": season, "limit": limit}).mappings().all()


def get_player_comparison(db: Session, season: str, player1_id: int, player2_id: int):
    sql = text(
        """
        select p.id as player_id,
               p.full_name,
               s.season,
               s.team_id,
               s.games_played,
               s.minutes,
               s.points,
               s.rebounds,
               s.assists,
               s.steals,
               s.blocks,
               s.turnovers
        from player_season_stats s
        join players p on p.id = s.player_id
        where s.season = :season
          and s.player_id in :player_ids
        order by p.full_name
        """
    ).bindparams(bindparam("player_ids", expanding=True))

    params = {
        "season": season,
        "player_ids": [player1_id, player2_id],
    }
    return db.execute(sql, params).mappings().all()


def get_shot_profile(db: Session, player_id: int):
    sql = text(
        """
        select shot_zone_basic,
               shot_zone_area,
               shot_zone_range,
               count(*) as attempts,
               sum(case when shot_made then 1 else 0 end) as made,
               round(
                   sum(case when shot_made then 1 else 0 end)::numeric
                   / nullif(count(*), 0),
                   4
               ) as pct
        from shot_charts
        where player_id = :player_id
        group by shot_zone_basic, shot_zone_area, shot_zone_range
        order by attempts desc
        """
    )
    return db.execute(sql, {"player_id": player_id}).mappings().all()
