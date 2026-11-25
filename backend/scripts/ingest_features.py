"""Create the feature tables and fill them from the NBA API. Safe to run again.

    python scripts/ingest_features.py            everything
    python scripts/ingest_features.py schema     only the tables
    python scripts/ingest_features.py box periods advanced matchups pairs   any subset
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psycopg2.extras import execute_values

from db_utils import engine

SEASON = "2024-25"
TIMEOUT = 90
MIN_MATCHUP_POSSESSIONS = 5


def clean(value):
    if hasattr(value, "item"):
        value = value.item()
    return None if isinstance(value, float) and math.isnan(value) else value


def whole(value):
    value = clean(value)
    return 0 if value is None else int(value)


def number(value):
    value = clean(value)
    return 0.0 if value is None else float(value)


def replace_season(table: str, columns: list[str], rows: list[tuple]):
    """Swap one season's rows inside a transaction, so readers never see a gap."""
    if not rows:
        raise RuntimeError(f"No rows fetched for {table}; nothing was changed.")
    with engine.begin() as conn:
        with conn.connection.cursor() as cursor:
            cursor.execute(f"delete from {table} where season = %s", (SEASON,))
            execute_values(cursor, f"insert into {table} ({', '.join(columns)}) values %s", rows, page_size=2000)
    print(f"{table}: {len(rows)} rows")


def player_ids() -> dict[int, int]:
    with engine.connect() as conn:
        return {r[0]: r[1] for r in conn.exec_driver_sql("select nba_player_id, id from players")}


def create_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql((Path(__file__).parent / "schema_features.sql").read_text(encoding="utf-8"))
    print("schema ready")


def ingest_box():
    from nba_api.stats.endpoints import leaguegamelog

    ids = player_ids()
    teams = leaguegamelog.LeagueGameLog(season=SEASON, player_or_team_abbreviation="T", timeout=TIMEOUT).get_data_frames()[0].to_dict("records")
    by_game: dict[str, list[dict]] = {}
    for row in teams:
        by_game.setdefault(row["GAME_ID"], []).append(row)
    with engine.connect() as conn:
        # At neutral sites the API marks no single home team; shot charts store "HOME vs AWAY".
        hosts = {r[0]: r[1].split(" vs ")[0] for r in conn.exec_driver_sql("select distinct nba_game_id, matchup from shot_charts")}
    team_rows = []
    for pair in by_game.values():
        if len(pair) != 2:
            continue
        for own, other in (pair, pair[::-1]):
            home = [" vs. " in r["MATCHUP"] for r in (own, other)]
            is_home = home[0] if home[0] != home[1] else own["TEAM_ABBREVIATION"] == hosts.get(own["GAME_ID"])
            team_rows.append((
                own["GAME_ID"], SEASON, own["GAME_DATE"], whole(own["TEAM_ID"]), whole(other["TEAM_ID"]),
                is_home, own["WL"] == "W", whole(own["PTS"]), whole(other["PTS"]),
                *(whole(own[k]) for k in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN")),
            ))
    replace_season("team_box_scores", ["nba_game_id", "season", "game_date", "nba_team_id", "opponent_nba_team_id", "is_home", "won", "points", "opponent_points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "minutes"], team_rows)

    players = leaguegamelog.LeagueGameLog(season=SEASON, player_or_team_abbreviation="P", timeout=TIMEOUT).get_data_frames()[0].to_dict("records")
    unknown = {r["PLAYER_NAME"] for r in players if r["PLAYER_ID"] not in ids}
    if unknown:
        print("players missing from the database, skipped:", sorted(unknown))
    replace_season("player_box_scores", ["nba_game_id", "player_id", "season", "game_date", "nba_team_id", "minutes", "points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "plus_minus"], [
        (r["GAME_ID"], ids[r["PLAYER_ID"]], SEASON, r["GAME_DATE"], whole(r["TEAM_ID"]),
         *(whole(r[k]) for k in ("MIN", "PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PLUS_MINUS")))
        for r in players if r["PLAYER_ID"] in ids
    ])


def ingest_periods():
    """Points per quarter and overtime, free throws included."""
    from nba_api.stats.endpoints import teamgamelogs

    rows = []
    for period in range(1, 11):
        frame = teamgamelogs.TeamGameLogs(season_nullable=SEASON, season_type_nullable="Regular Season", period_nullable=str(period), timeout=TIMEOUT).get_data_frames()[0]
        if frame.empty:
            break
        rows += [(r["GAME_ID"], whole(r["TEAM_ID"]), SEASON, period, *(whole(r[k]) for k in ("PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "TOV"))) for r in frame.to_dict("records")]
        time.sleep(1)
    replace_season("team_period_scores", ["nba_game_id", "nba_team_id", "season", "period", "points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "tov"], rows)


def ingest_advanced():
    from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashptdefend

    ids = player_ids()
    advanced = leaguedashplayerstats.LeagueDashPlayerStats(season=SEASON, measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame", timeout=TIMEOUT).get_data_frames()[0].to_dict("records")
    time.sleep(1)
    defend = leaguedashptdefend.LeagueDashPtDefend(season=SEASON, per_mode_simple="Totals", defense_category="Overall", timeout=TIMEOUT).get_data_frames()[0].to_dict("records")
    guarded = {r["CLOSE_DEF_PERSON_ID"]: r for r in defend}
    rows = []
    for r in advanced:
        if r["PLAYER_ID"] not in ids:
            continue
        d = guarded.get(r["PLAYER_ID"], {})
        rows.append((
            ids[r["PLAYER_ID"]], SEASON, whole(r["AGE"]),
            *(clean(r[k]) for k in ("OFF_RATING", "DEF_RATING", "NET_RATING", "AST_PCT", "AST_TO", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT", "TS_PCT", "USG_PCT", "PACE", "PIE")),
            whole(r["POSS"]), clean(d.get("D_FGA")), clean(d.get("D_FG_PCT")), clean(d.get("PCT_PLUSMINUS")),
        ))
    replace_season("player_advanced_stats", ["player_id", "season", "season_age", "off_rating", "def_rating", "net_rating", "ast_pct", "ast_to", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "efg_pct", "ts_pct", "usg_pct", "pace", "pie", "possessions", "defended_fga", "defended_fg_pct", "defended_fg_diff"], rows)


def ingest_matchups():
    from nba_api.stats.endpoints import leagueseasonmatchups

    ids = player_ids()
    with engine.connect() as conn:
        shooters = [r[0] for r in conn.exec_driver_sql("select p.nba_player_id from player_season_stats s join players p on p.id = s.player_id order by 1")]
    merged: dict[tuple[int, int], list[float]] = {}
    failed = []
    for n, nba_id in enumerate(shooters, 1):
        for attempt in range(4):
            try:
                frame = leagueseasonmatchups.LeagueSeasonMatchups(season=SEASON, per_mode_simple="Totals", off_player_id_nullable=str(nba_id), timeout=40).get_data_frames()[0]
                break
            except Exception as error:  # the API throttles now and then
                print(f"retry {nba_id}: {type(error).__name__}")
                time.sleep(4 * (attempt + 1))
        else:
            failed.append(nba_id)
            continue
        for r in frame.to_dict("records"):
            if r["DEF_PLAYER_ID"] not in ids or number(r["PARTIAL_POSS"]) <= 0:
                continue
            key = (ids[nba_id], ids[r["DEF_PLAYER_ID"]])
            values = [number(r[k]) for k in ("GP", "MATCHUP_TIME_SEC", "PARTIAL_POSS", "PLAYER_PTS", "TEAM_PTS", "MATCHUP_AST", "MATCHUP_TOV", "MATCHUP_BLK", "MATCHUP_FGM", "MATCHUP_FGA", "MATCHUP_FG3M", "MATCHUP_FG3A", "MATCHUP_FTM", "MATCHUP_FTA")]
            merged[key] = [a + b for a, b in zip(merged[key], values)] if key in merged else values
        if n % 50 == 0:
            print(f"{n}/{len(shooters)} players, {len(merged)} pairs", flush=True)
        time.sleep(0.5)
    if failed:
        print("no matchups for:", failed)
    replace_season("player_matchups", ["season", "off_player_id", "def_player_id", "games", "seconds", "possessions", "points", "team_points", "ast", "tov", "blk", "fgm", "fga", "tpm", "tpa", "ftm", "fta"], [
        (SEASON, off, guard, int(v[0]), int(v[1]), *v[2:]) for (off, guard), v in merged.items() if v[2] >= MIN_MATCHUP_POSSESSIONS
    ])


def ingest_pairs():
    from nba_api.stats.endpoints import leaguedashlineups

    ids = player_ids()
    with engine.connect() as conn:
        teams = [r[0] for r in conn.exec_driver_sql("select nba_team_id from teams order by 1")]
    rows = {}
    for team in teams:
        for attempt in range(4):
            try:
                frame = leaguedashlineups.LeagueDashLineups(season=SEASON, group_quantity="2", team_id_nullable=str(team), measure_type_detailed_defense="Advanced", per_mode_detailed="Totals", timeout=60).get_data_frames()[0]
                break
            except Exception as error:
                print(f"retry team {team}: {type(error).__name__}")
                time.sleep(4 * (attempt + 1))
        else:
            raise RuntimeError(f"Could not fetch pairs for team {team}")
        for r in frame.to_dict("records"):
            pair = [int(p) for p in str(r["GROUP_ID"]).strip("-").split("-") if p.strip()]
            if len(pair) != 2 or any(p not in ids for p in pair):
                continue
            a, b = sorted(ids[p] for p in pair)
            rows[(team, a, b)] = (SEASON, team, a, b, whole(r["GP"]), number(r["MIN"]), whole(r.get("POSS")), clean(r["OFF_RATING"]), clean(r["DEF_RATING"]), clean(r["NET_RATING"]))
        time.sleep(0.6)
    replace_season("player_pairs", ["season", "nba_team_id", "player_a", "player_b", "games", "minutes", "possessions", "off_rating", "def_rating", "net_rating"], list(rows.values()))


STEPS = {"schema": create_schema, "box": ingest_box, "periods": ingest_periods, "advanced": ingest_advanced, "matchups": ingest_matchups, "pairs": ingest_pairs}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(STEPS)
    for name in chosen:
        STEPS[name]()
