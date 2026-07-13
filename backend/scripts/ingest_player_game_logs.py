import time

from sqlalchemy import text
from nba_api.stats.endpoints import playergamelog

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


def get_or_create_game(conn, nba_game_id: str, season: str, game_date):
    result = conn.execute(
        text(
            """
            insert into games (
                nba_game_id,
                season,
                game_date
            )
            values (
                :nba_game_id,
                :season,
                :game_date
            )
            on conflict (nba_game_id)
            do update set
                season = excluded.season,
                game_date = excluded.game_date
            returning id;
            """
        ),
        {
            "nba_game_id": nba_game_id,
            "season": season,
            "game_date": game_date,
        },
    )

    return result.scalar()


def ingest_player_game_logs(season: str = SEASON, player_limit: int | None = None):
    with engine.begin() as conn:
        players = get_players(conn, player_limit)

    print(f"Fetching game logs for {len(players)} players...")

    total_rows = 0

    total_players = len(players)

    for index, player in enumerate(players, start=1):
        print(f"Fetching {player['full_name']} ({index}/{total_players})...")

        try:
            endpoint = playergamelog.PlayerGameLog(
                player_id=player["nba_player_id"],
                season=season,
                season_type_all_star="Regular Season",
            )

            df = endpoint.get_data_frames()[0]
            player_rows = 0

            with engine.begin() as conn:
                for _, row in df.iterrows():
                    game_id = get_or_create_game(
                        conn,
                        nba_game_id=str(row["Game_ID"]),
                        season=season,
                        game_date=row["GAME_DATE"],
                    )

                    conn.execute(
                        text(
                            """
                            insert into player_game_logs (
                                player_id,
                                game_id,
                                season,
                                minutes,
                                points,
                                rebounds,
                                assists,
                                steals,
                                blocks,
                                turnovers,
                                field_goals_made,
                                field_goals_attempted,
                                three_pointers_made,
                                three_pointers_attempted,
                                free_throws_made,
                                free_throws_attempted,
                                plus_minus
                            )
                            values (
                                :player_id,
                                :game_id,
                                :season,
                                :minutes,
                                :points,
                                :rebounds,
                                :assists,
                                :steals,
                                :blocks,
                                :turnovers,
                                :field_goals_made,
                                :field_goals_attempted,
                                :three_pointers_made,
                                :three_pointers_attempted,
                                :free_throws_made,
                                :free_throws_attempted,
                                :plus_minus
                            )
                            on conflict (player_id, game_id)
                            do update set
                                minutes = excluded.minutes,
                                points = excluded.points,
                                rebounds = excluded.rebounds,
                                assists = excluded.assists,
                                steals = excluded.steals,
                                blocks = excluded.blocks,
                                turnovers = excluded.turnovers,
                                field_goals_made = excluded.field_goals_made,
                                field_goals_attempted = excluded.field_goals_attempted,
                                three_pointers_made = excluded.three_pointers_made,
                                three_pointers_attempted = excluded.three_pointers_attempted,
                                free_throws_made = excluded.free_throws_made,
                                free_throws_attempted = excluded.free_throws_attempted,
                                plus_minus = excluded.plus_minus;
                            """
                        ),
                        {
                            "player_id": player["id"],
                            "game_id": game_id,
                            "season": season,
                            "minutes": str(row["MIN"]),
                            "points": int(row["PTS"]),
                            "rebounds": int(row["REB"]),
                            "assists": int(row["AST"]),
                            "steals": int(row["STL"]),
                            "blocks": int(row["BLK"]),
                            "turnovers": int(row["TOV"]),
                            "field_goals_made": int(row["FGM"]),
                            "field_goals_attempted": int(row["FGA"]),
                            "three_pointers_made": int(row["FG3M"]),
                            "three_pointers_attempted": int(row["FG3A"]),
                            "free_throws_made": int(row["FTM"]),
                            "free_throws_attempted": int(row["FTA"]),
                            "plus_minus": int(row["PLUS_MINUS"]) if row["PLUS_MINUS"] is not None else None,
                        },
                    )

                    total_rows += 1
                    player_rows += 1

            print(
                f"Upserted {player_rows} rows for {player['full_name']}. "
                f"Total rows: {total_rows}"
            )
            time.sleep(0.7)

        except Exception as e:
            print(f"Failed for {player['full_name']}: {e}")

    print(f"Done. Upserted {total_rows} game log rows.")


if __name__ == "__main__":
    ingest_player_game_logs()
