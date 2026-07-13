import time

from sqlalchemy import text
from nba_api.stats.endpoints import shotchartdetail

from db_utils import engine

SEASON = "2024-25"


def get_players(conn, limit: int | None):
    base_sql = """
        select id, nba_player_id, full_name
        from players
        where is_active = true
        order by full_name
    """

    if limit is None:
        return conn.execute(text(base_sql)).mappings().all()

    return conn.execute(
        text(f"{base_sql} limit :limit"),
        {"limit": limit},
    ).mappings().all()


def get_team_id_by_nba_team_id(conn, nba_team_id):
    result = conn.execute(
        text("select id from teams where nba_team_id = :nba_team_id"),
        {"nba_team_id": int(nba_team_id)},
    ).scalar()

    return result


def ingest_shot_charts(season: str = SEASON, player_limit: int | None = None):
    with engine.begin() as conn:
        players = get_players(conn, player_limit)

    print(f"Fetching shot charts for {len(players)} players...")

    total_rows = 0
    total_players = len(players)

    for index, player in enumerate(players, start=1):
        print(f"Fetching shots for {player['full_name']} ({index}/{total_players})...")

        try:
            endpoint = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=player["nba_player_id"],
                season_nullable=season,
                season_type_all_star="Regular Season",
                context_measure_simple="FGA",
            )

            df = endpoint.get_data_frames()[0]
            player_rows = 0

            with engine.begin() as conn:
                for _, row in df.iterrows():
                    team_id = get_team_id_by_nba_team_id(conn, row["TEAM_ID"])

                    conn.execute(
                        text(
                            """
                            insert into shot_charts (
                                player_id,
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
                                game_date,
                                matchup
                            )
                            values (
                                :player_id,
                                :nba_player_id,
                                :nba_game_id,
                                :season,
                                :team_id,
                                :period,
                                :minutes_remaining,
                                :seconds_remaining,
                                :event_type,
                                :action_type,
                                :shot_type,
                                :shot_zone_basic,
                                :shot_zone_area,
                                :shot_zone_range,
                                :shot_distance,
                                :loc_x,
                                :loc_y,
                                :shot_made,
                                :game_date,
                                :matchup
                            )
                            on conflict (nba_player_id, nba_game_id, period, minutes_remaining, seconds_remaining, loc_x, loc_y)
                            do nothing;
                            """
                        ),
                        {
                            "player_id": player["id"],
                            "nba_player_id": player["nba_player_id"],
                            "nba_game_id": str(row["GAME_ID"]),
                            "season": season,
                            "team_id": team_id,
                            "period": int(row["PERIOD"]),
                            "minutes_remaining": int(row["MINUTES_REMAINING"]),
                            "seconds_remaining": int(row["SECONDS_REMAINING"]),
                            "event_type": row["EVENT_TYPE"],
                            "action_type": row["ACTION_TYPE"],
                            "shot_type": row["SHOT_TYPE"],
                            "shot_zone_basic": row["SHOT_ZONE_BASIC"],
                            "shot_zone_area": row["SHOT_ZONE_AREA"],
                            "shot_zone_range": row["SHOT_ZONE_RANGE"],
                            "shot_distance": int(row["SHOT_DISTANCE"]),
                            "loc_x": int(row["LOC_X"]),
                            "loc_y": int(row["LOC_Y"]),
                            "shot_made": bool(row["SHOT_MADE_FLAG"]),
                            "game_date": row["GAME_DATE"],
                            "matchup": row["HTM"] + " vs " + row["VTM"],
                        },
                    )

                    total_rows += 1
                    player_rows += 1

            print(
                f"Upserted {player_rows} shots for {player['full_name']}. "
                f"Total shots: {total_rows}"
            )
            time.sleep(1.0)

        except Exception as e:
            print(f"Failed for {player['full_name']}: {e}")

    print(f"Done. Inserted/upserted {total_rows} shot rows.")


if __name__ == "__main__":
    ingest_shot_charts()
