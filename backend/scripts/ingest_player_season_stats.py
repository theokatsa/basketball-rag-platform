import time

from sqlalchemy import text
from nba_api.stats.endpoints import leaguedashplayerstats

from db_utils import engine

SEASON = "2024-25"


def get_team_id_map(conn):
    rows = conn.execute(text("select id, nba_team_id from teams")).mappings().all()
    return {row["nba_team_id"]: row["id"] for row in rows}


def get_player_id_map(conn):
    rows = conn.execute(text("select id, nba_player_id from players")).mappings().all()
    return {row["nba_player_id"]: row["id"] for row in rows}


def ingest_player_season_stats(season: str = SEASON):
    print(f"Fetching player season stats for {season}...")

    endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )

    df = endpoint.get_data_frames()[0]
    print(f"Fetched {len(df)} player stat rows.")

    with engine.begin() as conn:
        team_map = get_team_id_map(conn)
        player_map = get_player_id_map(conn)

        inserted = 0

        for _, row in df.iterrows():
            nba_player_id = int(row["PLAYER_ID"])
            nba_team_id = int(row["TEAM_ID"])

            player_id = player_map.get(nba_player_id)
            team_id = team_map.get(nba_team_id)

            if not player_id:
                continue

            conn.execute(
                text(
                    """
                    insert into player_season_stats (
                        player_id,
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
                    )
                    values (
                        :player_id,
                        :season,
                        :team_id,
                        :games_played,
                        :minutes,
                        :points,
                        :rebounds,
                        :assists,
                        :steals,
                        :blocks,
                        :turnovers,
                        :field_goal_pct,
                        :three_point_pct,
                        :free_throw_pct
                    )
                    on conflict (player_id, season, team_id)
                    do update set
                        games_played = excluded.games_played,
                        minutes = excluded.minutes,
                        points = excluded.points,
                        rebounds = excluded.rebounds,
                        assists = excluded.assists,
                        steals = excluded.steals,
                        blocks = excluded.blocks,
                        turnovers = excluded.turnovers,
                        field_goal_pct = excluded.field_goal_pct,
                        three_point_pct = excluded.three_point_pct,
                        free_throw_pct = excluded.free_throw_pct;
                    """
                ),
                {
                    "player_id": player_id,
                    "season": season,
                    "team_id": team_id,
                    "games_played": int(row["GP"]),
                    "minutes": float(row["MIN"]),
                    "points": float(row["PTS"]),
                    "rebounds": float(row["REB"]),
                    "assists": float(row["AST"]),
                    "steals": float(row["STL"]),
                    "blocks": float(row["BLK"]),
                    "turnovers": float(row["TOV"]),
                    "field_goal_pct": float(row["FG_PCT"]),
                    "three_point_pct": float(row["FG3_PCT"]),
                    "free_throw_pct": float(row["FT_PCT"]),
                },
            )

            inserted += 1

    print(f"Upserted {inserted} player season stat rows.")


if __name__ == "__main__":
    ingest_player_season_stats()
