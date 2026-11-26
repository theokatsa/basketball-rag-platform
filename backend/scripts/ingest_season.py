"""One NBA season (regular season, or play-in and playoffs) from the NBA API, into Supabase or into local Parquet files. Safe to run again.

    python scripts/ingest_season.py --season 2025-26                       every step, into the database
    python scripts/ingest_season.py --season 2023-24 --local ../data        into ../data/2023-24/<table>.parquet
    python scripts/ingest_season.py --season 2025-26 box advanced           only these steps
    python scripts/ingest_season.py --season 2025-26 --postseason           the play-in and the playoffs, into postseason_<table>

Steps, in this order: (schema) stats shots box logs periods advanced matchups pairs ("teams": team results only; "logs": the older games and
player_game_logs tables, rebuilt from the box scores).
Every step fetches the whole season and swaps that season's rows in one transaction (the database), or
rewrites one file (local), so a step can be repeated after a failure and readers never see half a season.
Players must already be in the players table (it holds every NBA player; scripts/ingest_players.py adds
new ones). The app reads ACTIVE_SEASON only, so loading a season changes nothing on the site by itself.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_utils import engine  # noqa: E402

TIMEOUT = 90
MIN_MATCHUP_POSSESSIONS = 5
STEPS = ["schema", "stats", "shots", "box", "teams", "logs", "periods", "advanced", "matchups", "pairs"]
DEFAULT = ["stats", "shots", "box", "logs", "periods", "advanced", "matchups", "pairs"]  # "teams" is part of "box"; alone, it loads only team results


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


def fetch(make, label: str, tries: int = 5):
    """The API throttles and times out now and then: wait longer each time, then give up loudly."""
    for attempt in range(tries):
        try:
            return make().get_data_frames()[0]
        except Exception as error:  # noqa: BLE001
            wait = 5 * (attempt + 1)
            print(f"  retry {label} in {wait}s: {type(error).__name__}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"The NBA API did not answer for {label}")


# ------------------------------------------------------------------ where the rows go

REGULAR = "Regular Season"
POSTSEASON = ["PlayIn", "Playoffs"]


class Sink:
    """Where a season's rows go. kind is the NBA's season type: regular-season rows go to the usual tables,
    play-in and playoff rows to postseason_<table>, with a season_type column, so they are never mixed."""

    kind = REGULAR

    def table(self, name: str) -> str:
        return name if self.kind == REGULAR else f"postseason_{name}"

    def typed(self, columns: list[str], rows: list[tuple]) -> tuple[list[str], list[tuple]]:
        return (columns, rows) if self.kind == REGULAR else (columns + ["season_type"], [(*r, self.kind) for r in rows])

    def empty(self, name: str) -> bool:
        """A regular season always has rows; a play-in may have none for some tables (no lineups to speak of)."""
        if self.kind == REGULAR:
            raise RuntimeError(f"No rows fetched for {name}; nothing was changed.")
        print(f"{self.table(name)}: nothing for {self.kind} {self.season}, skipped", flush=True)
        return True


class Database(Sink):
    def __init__(self, season: str):
        self.season = season

    def replace(self, table: str, columns: list[str], rows: list[tuple], conflict: str = ""):
        if not rows and self.empty(table):
            return
        name, (columns, rows) = self.table(table), self.typed(columns, rows)
        where, params = ("season = %s", (self.season,)) if self.kind == REGULAR else ("season = %s and season_type = %s", (self.season, self.kind))
        with engine.begin() as conn:
            with conn.connection.cursor() as cursor:
                cursor.execute(f"delete from {name} where {where}", params)
                execute_values(cursor, f"insert into {name} ({', '.join(columns)}) values %s {conflict}", rows, page_size=2000)
        print(f"{name}: {len(rows)} rows for {self.season}{'' if self.kind == REGULAR else ' ' + self.kind}", flush=True)

    def read(self, table: str, columns: list[str]) -> pd.DataFrame:
        where, params = ("season = :s", {"s": self.season}) if self.kind == REGULAR else ("season = :s and season_type = :k", {"s": self.season, "k": self.kind})
        with engine.connect() as conn:
            return pd.DataFrame(conn.execute(text(f"select {', '.join(columns)} from {self.table(table)} where {where}"), params).all(), columns=columns)

    def size(self) -> str:
        with engine.connect() as conn:
            return conn.execute(text("select pg_size_pretty(pg_database_size(current_database()))")).scalar()


class Local(Sink):
    def __init__(self, root: Path, season: str):
        self.season, self.folder = season, root / season
        self.folder.mkdir(parents=True, exist_ok=True)

    def replace(self, table: str, columns: list[str], rows: list[tuple], conflict: str = ""):
        if not rows and self.empty(table):
            return
        name, (columns, rows) = self.table(table), self.typed(columns, rows)
        frame = pd.DataFrame(rows, columns=columns)
        if conflict and table == "shot_charts":
            frame = frame.drop_duplicates(["nba_player_id", "nba_game_id", "period", "minutes_remaining", "seconds_remaining", "loc_x", "loc_y"])
        path = self.folder / f"{name}.parquet"
        if self.kind != REGULAR and path.exists():  # one file holds play-in and playoffs: replace only this kind
            kept = pd.read_parquet(path)
            frame = pd.concat([kept[kept.season_type != self.kind], frame], ignore_index=True)
        frame.to_parquet(path, index=False)
        print(f"{name}: {len(rows)} rows -> {path}", flush=True)

    def read(self, table: str, columns: list[str]) -> pd.DataFrame:
        path = self.folder / f"{self.table(table)}.parquet"
        if not path.exists():
            return pd.DataFrame(columns=columns)
        frame = pd.read_parquet(path)
        return (frame if self.kind == REGULAR else frame[frame.season_type == self.kind])[columns]

    def size(self) -> str:
        return f"{sum(f.stat().st_size for f in self.folder.glob('*.parquet')) / 1e6:.1f} MB in {self.folder}"


# ------------------------------------------------------------------ lookups (read from the database, never changed)

def player_ids() -> dict[int, int]:
    with engine.connect() as conn:
        return {r[0]: r[1] for r in conn.exec_driver_sql("select nba_player_id, id from players")}


def team_ids() -> dict[int, int]:
    with engine.connect() as conn:
        return {r[0]: r[1] for r in conn.exec_driver_sql("select nba_team_id, id from teams")}


def missing(rows: list[dict], key: str, known: dict, name: str) -> None:
    unknown = sorted({str(r[name]) for r in rows if r[key] not in known})
    if unknown:
        print(f"  not in the players table, skipped ({len(unknown)}): {', '.join(unknown[:12])}{' ...' if len(unknown) > 12 else ''}")


# ------------------------------------------------------------------ steps

def create_schema(season: str, sink):
    """The tables of the season data (scripts/schema_features.sql); for a new database. Safe to run again."""
    with engine.begin() as conn:
        conn.exec_driver_sql((Path(__file__).parent / "schema_features.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql((Path(__file__).parent / "schema_postseason.sql").read_text(encoding="utf-8"))
    print("schema ready", flush=True)


def ingest_stats(season: str, sink):
    from nba_api.stats.endpoints import leaguedashplayerstats

    ids, teams = player_ids(), team_ids()
    frame = fetch(lambda: leaguedashplayerstats.LeagueDashPlayerStats(season=season, season_type_all_star=sink.kind, per_mode_detailed="PerGame", timeout=TIMEOUT), "season stats")
    records = frame.to_dict("records")
    missing(records, "PLAYER_ID", ids, "PLAYER_NAME")
    sink.replace("player_season_stats", ["player_id", "season", "team_id", "games_played", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "field_goal_pct", "three_point_pct", "free_throw_pct"], [
        (ids[r["PLAYER_ID"]], season, teams.get(whole(r["TEAM_ID"])), whole(r["GP"]), *(number(r[k]) for k in ("MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV")), *(clean(r[k]) for k in ("FG_PCT", "FG3_PCT", "FT_PCT")))
        for r in records if r["PLAYER_ID"] in ids
    ])


def ingest_shots(season: str, sink):
    """Every shot of the season, one call per team (the old script asked once per player and wrote one shot at a time)."""
    from nba_api.stats.endpoints import shotchartdetail

    ids, teams = player_ids(), team_ids()
    rows, seen = [], []
    for n, team in enumerate(sorted(teams), 1):
        frame = fetch(lambda: shotchartdetail.ShotChartDetail(team_id=team, player_id=0, season_nullable=season, season_type_all_star=sink.kind, context_measure_simple="FGA", timeout=TIMEOUT), f"shots of team {team}")
        records = frame.to_dict("records")
        seen += records
        rows += [(
            ids[r["PLAYER_ID"]], int(r["PLAYER_ID"]), str(r["GAME_ID"]), season, teams.get(whole(r["TEAM_ID"])), whole(r["PERIOD"]), whole(r["MINUTES_REMAINING"]), whole(r["SECONDS_REMAINING"]),
            r["EVENT_TYPE"], r["ACTION_TYPE"], r["SHOT_TYPE"], r["SHOT_ZONE_BASIC"], r["SHOT_ZONE_AREA"], r["SHOT_ZONE_RANGE"], whole(r["SHOT_DISTANCE"]), whole(r["LOC_X"]), whole(r["LOC_Y"]),
            bool(r["SHOT_MADE_FLAG"]), pd.to_datetime(str(r["GAME_DATE"])).date(), f"{r['HTM']} vs {r['VTM']}",
        ) for r in records if r["PLAYER_ID"] in ids]
        print(f"  {n}/{len(teams)} teams, {len(rows)} shots", flush=True)
        time.sleep(0.8)
    missing(seen, "PLAYER_ID", ids, "PLAYER_NAME")
    sink.replace("shot_charts", ["player_id", "nba_player_id", "nba_game_id", "season", "team_id", "period", "minutes_remaining", "seconds_remaining", "event_type", "action_type", "shot_type",
                                 "shot_zone_basic", "shot_zone_area", "shot_zone_range", "shot_distance", "loc_x", "loc_y", "shot_made", "game_date", "matchup"], rows,
                 conflict="on conflict (nba_player_id, nba_game_id, period, minutes_remaining, seconds_remaining, loc_x, loc_y) do nothing")


def ingest_box(season: str, sink):
    ingest_team_box(season, sink)
    time.sleep(1)
    ingest_player_box(season, sink)


def ingest_team_box(season: str, sink):
    """Team box scores only: a season's results and records (about 1 MB)."""
    from nba_api.stats.endpoints import leaguegamelog

    teams = fetch(lambda: leaguegamelog.LeagueGameLog(season=season, player_or_team_abbreviation="T", season_type_all_star=sink.kind, timeout=TIMEOUT), "team game logs").to_dict("records")
    by_game: dict[str, list[dict]] = {}
    for row in teams:
        by_game.setdefault(row["GAME_ID"], []).append(row)
    # At neutral sites the API marks no single home team; shot charts store "HOME vs AWAY".
    shots = sink.read("shot_charts", ["nba_game_id", "matchup"]).drop_duplicates("nba_game_id")
    hosts = {g: m.split(" vs ")[0] for g, m in zip(shots["nba_game_id"], shots["matchup"])}
    team_rows, unsure = [], 0
    for pair in by_game.values():
        if len(pair) != 2:
            continue
        for own, other in (pair, pair[::-1]):
            home = [" vs. " in r["MATCHUP"] for r in (own, other)]
            if home[0] == home[1] and own["GAME_ID"] not in hosts:
                unsure += 1
            is_home = home[0] if home[0] != home[1] else own["TEAM_ABBREVIATION"] == hosts.get(own["GAME_ID"])
            team_rows.append((
                own["GAME_ID"], season, own["GAME_DATE"], whole(own["TEAM_ID"]), whole(other["TEAM_ID"]), is_home, own["WL"] == "W", whole(own["PTS"]), whole(other["PTS"]),
                *(whole(own[k]) for k in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN")),
            ))
    if unsure:
        print(f"  {unsure // 2} neutral-site games without shots to tell the home team: run the shots step first")
    sink.replace("team_box_scores", ["nba_game_id", "season", "game_date", "nba_team_id", "opponent_nba_team_id", "is_home", "won", "points", "opponent_points", "fgm", "fga", "tpm", "tpa",
                                     "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "minutes"], team_rows)


def ingest_player_box(season: str, sink):
    from nba_api.stats.endpoints import leaguegamelog

    ids = player_ids()
    players = fetch(lambda: leaguegamelog.LeagueGameLog(season=season, player_or_team_abbreviation="P", season_type_all_star=sink.kind, timeout=TIMEOUT), "player game logs").to_dict("records")
    missing(players, "PLAYER_ID", ids, "PLAYER_NAME")
    sink.replace("player_box_scores", ["nba_game_id", "player_id", "season", "game_date", "nba_team_id", "minutes", "points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast",
                                       "stl", "blk", "tov", "pf", "plus_minus"], [
        (r["GAME_ID"], ids[r["PLAYER_ID"]], season, r["GAME_DATE"], whole(r["TEAM_ID"]),
         *(whole(r[k]) for k in ("MIN", "PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PLUS_MINUS")))
        for r in players if r["PLAYER_ID"] in ids
    ])


def ingest_periods(season: str, sink):
    """Points per quarter and overtime, free throws included."""
    from nba_api.stats.endpoints import teamgamelogs

    rows = []
    for period in range(1, 11):
        frame = fetch(lambda: teamgamelogs.TeamGameLogs(season_nullable=season, season_type_nullable=sink.kind, period_nullable=str(period), timeout=TIMEOUT), f"period {period}")
        if frame.empty:
            break
        rows += [(r["GAME_ID"], whole(r["TEAM_ID"]), season, period, *(whole(r[k]) for k in ("PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "TOV"))) for r in frame.to_dict("records")]
        time.sleep(1)
    sink.replace("team_period_scores", ["nba_game_id", "nba_team_id", "season", "period", "points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "tov"], rows)


def ingest_advanced(season: str, sink):
    from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashptdefend

    ids = player_ids()
    advanced = fetch(lambda: leaguedashplayerstats.LeagueDashPlayerStats(season=season, measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame", season_type_all_star=sink.kind, timeout=TIMEOUT), "advanced").to_dict("records")
    time.sleep(1)
    defend = fetch(lambda: leaguedashptdefend.LeagueDashPtDefend(season=season, per_mode_simple="Totals", defense_category="Overall", season_type_all_star=sink.kind, timeout=TIMEOUT), "defense").to_dict("records")
    guarded = {r["CLOSE_DEF_PERSON_ID"]: r for r in defend}
    rows = []
    for r in advanced:
        if r["PLAYER_ID"] not in ids:
            continue
        d = guarded.get(r["PLAYER_ID"], {})
        rows.append((
            ids[r["PLAYER_ID"]], season, whole(r["AGE"]),
            *(clean(r[k]) for k in ("OFF_RATING", "DEF_RATING", "NET_RATING", "AST_PCT", "AST_TO", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT", "TS_PCT", "USG_PCT", "PACE", "PIE")),
            whole(r["POSS"]), clean(d.get("D_FGA")), clean(d.get("D_FG_PCT")), clean(d.get("PCT_PLUSMINUS")),
        ))
    sink.replace("player_advanced_stats", ["player_id", "season", "season_age", "off_rating", "def_rating", "net_rating", "ast_pct", "ast_to", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "efg_pct",
                                           "ts_pct", "usg_pct", "pace", "pie", "possessions", "defended_fga", "defended_fg_pct", "defended_fg_diff"], rows)


MATCHUP_COLUMNS = ["season", "off_player_id", "def_player_id", "games", "seconds", "possessions", "points", "team_points", "ast", "tov", "blk", "fgm", "fga", "tpm", "tpa", "ftm", "fta"]


def postseason_matchups(season: str, sink):
    """The season matchup endpoint has no play-in or playoff data, so the per-game matchup box scores are
    added up instead (one call per game). The season endpoint is itself a sum over games, so the two agree."""
    from nba_api.stats.endpoints import boxscorematchupsv3

    ids = player_ids()
    games = sorted(sink.read("team_box_scores", ["nba_game_id"])["nba_game_id"].astype(str).unique())
    if not games:
        raise RuntimeError("Run the box step first: matchups are fetched game by game.")
    merged: dict[tuple[int, int], list[float]] = {}
    for n, game in enumerate(games, 1):
        frame = fetch(lambda: boxscorematchupsv3.BoxScoreMatchupsV3(game_id=game, timeout=60), f"matchups of game {game}", tries=4)
        for r in frame.to_dict("records"):
            if r["personIdOff"] not in ids or r["personIdDef"] not in ids or number(r["partialPossessions"]) <= 0:
                continue
            key = (ids[r["personIdOff"]], ids[r["personIdDef"]])
            values = [1.0, number(r["matchupMinutesSort"]), *(number(r[k]) for k in ("partialPossessions", "playerPoints", "teamPoints", "matchupAssists", "matchupTurnovers", "matchupBlocks",
                      "matchupFieldGoalsMade", "matchupFieldGoalsAttempted", "matchupThreePointersMade", "matchupThreePointersAttempted", "matchupFreeThrowsMade", "matchupFreeThrowsAttempted"))]
            merged[key] = [a + b for a, b in zip(merged[key], values)] if key in merged else values
        if n % 20 == 0:
            print(f"  {n}/{len(games)} games, {len(merged)} pairs", flush=True)
        time.sleep(0.6)
    sink.replace("player_matchups", MATCHUP_COLUMNS, [(season, off, guard, int(v[0]), int(v[1]), *v[2:]) for (off, guard), v in merged.items() if v[2] >= MIN_MATCHUP_POSSESSIONS])


def ingest_matchups(season: str, sink):
    """Who guarded whom: one call per player who played that season (about 15 minutes)."""
    from nba_api.stats.endpoints import leagueseasonmatchups

    if sink.kind != REGULAR:
        return postseason_matchups(season, sink)

    ids = player_ids()
    internal = {v: k for k, v in ids.items()}
    played = sink.read("player_box_scores", ["player_id"])["player_id"].unique()
    if not len(played):
        raise RuntimeError("Run the box step first: matchups are fetched for the players of the season.")
    shooters = sorted(internal[int(p)] for p in played if int(p) in internal)
    merged: dict[tuple[int, int], list[float]] = {}
    failed = []
    for n, nba_id in enumerate(shooters, 1):
        try:
            frame = fetch(lambda: leagueseasonmatchups.LeagueSeasonMatchups(season=season, per_mode_simple="Totals", off_player_id_nullable=str(nba_id), timeout=40), f"matchups of {nba_id}", tries=4)
        except RuntimeError:
            failed.append(nba_id)
            continue
        for r in frame.to_dict("records"):
            if r["DEF_PLAYER_ID"] not in ids or number(r["PARTIAL_POSS"]) <= 0:
                continue
            key = (ids[nba_id], ids[r["DEF_PLAYER_ID"]])
            values = [number(r[k]) for k in ("GP", "MATCHUP_TIME_SEC", "PARTIAL_POSS", "PLAYER_PTS", "TEAM_PTS", "MATCHUP_AST", "MATCHUP_TOV", "MATCHUP_BLK", "MATCHUP_FGM", "MATCHUP_FGA",
                                             "MATCHUP_FG3M", "MATCHUP_FG3A", "MATCHUP_FTM", "MATCHUP_FTA")]
            merged[key] = [a + b for a, b in zip(merged[key], values)] if key in merged else values
        if n % 50 == 0:
            print(f"  {n}/{len(shooters)} players, {len(merged)} pairs", flush=True)
        time.sleep(0.5)
    if failed:
        print(f"  no matchups for {len(failed)} players: {failed[:20]}")
    sink.replace("player_matchups", MATCHUP_COLUMNS, [
        (season, off, guard, int(v[0]), int(v[1]), *v[2:]) for (off, guard), v in merged.items() if v[2] >= MIN_MATCHUP_POSSESSIONS
    ])


def ingest_pairs(season: str, sink):
    from nba_api.stats.endpoints import leaguedashlineups

    ids = player_ids()
    rows = {}
    for team in sorted(team_ids()):
        frame = fetch(lambda: leaguedashlineups.LeagueDashLineups(season=season, group_quantity="2", team_id_nullable=str(team), measure_type_detailed_defense="Advanced", per_mode_detailed="Totals", season_type_all_star=sink.kind, timeout=60), f"pairs of team {team}")
        for r in frame.to_dict("records"):
            pair = [int(p) for p in str(r["GROUP_ID"]).strip("-").split("-") if p.strip()]
            if len(pair) != 2 or any(p not in ids for p in pair):
                continue
            a, b = sorted(ids[p] for p in pair)
            rows[(team, a, b)] = (season, team, a, b, whole(r["GP"]), number(r["MIN"]), whole(r.get("POSS")), clean(r["OFF_RATING"]), clean(r["DEF_RATING"]), clean(r["NET_RATING"]))
        time.sleep(0.6)
    sink.replace("player_pairs", ["season", "nba_team_id", "player_a", "player_b", "games", "minutes", "possessions", "off_rating", "def_rating", "net_rating"], list(rows.values()))


def ingest_logs(season: str, sink):
    """The older tables "games" and "player_game_logs", rebuilt from the box scores of the season (no API calls).

    They hold the same NBA data in another shape and are still read by older endpoints. The 2024-25 games
    rows have no teams or scores; new seasons get them from the team box scores.
    """
    if sink.kind != REGULAR:
        print("  logs: the older games and player_game_logs tables are kept for the regular season only", flush=True)
        return
    team = sink.read("team_box_scores", ["nba_game_id", "game_date", "nba_team_id", "is_home", "points"])
    box = sink.read("player_box_scores", ["nba_game_id", "player_id", "minutes", "points", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "plus_minus"])
    if team.empty or box.empty:
        raise RuntimeError("Run the box step first: games and game logs are made from the box scores.")
    with engine.connect() as conn:
        teams = {r[0]: r[1] for r in conn.exec_driver_sql("select nba_team_id, id from teams")}
    games = []
    for game_id, sides in team.groupby("nba_game_id"):
        home, away = sides[sides.is_home], sides[~sides.is_home]
        h, a = (home.iloc[0] if len(home) else None), (away.iloc[0] if len(away) else None)
        games.append((str(game_id), season, pd.Timestamp(sides.game_date.iloc[0]).date(), teams.get(int(h.nba_team_id)) if h is not None else None,
                      teams.get(int(a.nba_team_id)) if a is not None else None, int(h.points) if h is not None else None, int(a.points) if a is not None else None))
    played = box[box.minutes > 0]
    columns = ["player_id", "game_id", "season", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "field_goals_made", "field_goals_attempted",
               "three_pointers_made", "three_pointers_attempted", "free_throws_made", "free_throws_attempted", "plus_minus"]

    def log_rows(ids: dict[str, int]):
        return [(int(r.player_id), ids[str(r.nba_game_id)], season, str(int(r.minutes)), *(int(getattr(r, k)) for k in ("points", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "plus_minus")))
                for r in played.itertuples() if str(r.nba_game_id) in ids]

    if isinstance(sink, Local):
        ids = {g[0]: n for n, g in enumerate(sorted(games), 1)}
        sink.replace("games", ["id", "nba_game_id", "season", "game_date", "home_team_id", "away_team_id", "home_score", "away_score"], [(ids[g[0]], *g) for g in sorted(games)])
        sink.replace("player_game_logs", columns, log_rows(ids))
        return
    with engine.begin() as conn:  # logs point at games by id: replace both together
        with conn.connection.cursor() as cursor:
            cursor.execute("delete from player_game_logs where season = %s", (season,))
            cursor.execute("delete from games where season = %s", (season,))
            execute_values(cursor, "insert into games (nba_game_id, season, game_date, home_team_id, away_team_id, home_score, away_score) values %s", games, page_size=2000)
            cursor.execute("select nba_game_id, id from games where season = %s", (season,))
            ids = dict(cursor.fetchall())
            rows = log_rows(ids)
            execute_values(cursor, f"insert into player_game_logs ({', '.join(columns)}) values %s", rows, page_size=2000)
    print(f"games: {len(games)} rows, player_game_logs: {len(rows)} rows for {season}", flush=True)


RUN = {"schema": create_schema, "logs": ingest_logs,"stats": ingest_stats, "shots": ingest_shots, "box": ingest_box, "teams": ingest_team_box, "periods": ingest_periods, "advanced": ingest_advanced, "matchups": ingest_matchups, "pairs": ingest_pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("steps", nargs="*", metavar="step", help=f"any of: {' '.join(STEPS)} (default: all)")
    parser.add_argument("--season", required=True)
    parser.add_argument("--local", type=Path, help="a folder: write Parquet files there instead of the database")
    parser.add_argument("--postseason", action="store_true", help="the play-in and the playoffs, into postseason_<table> (no older games and logs tables)")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}", args.season):
        sys.exit("--season looks like 2025-26")
    if unknown := [s for s in args.steps if s not in STEPS]:
        sys.exit(f"Unknown steps: {unknown}. Steps: {' '.join(STEPS)}")
    steps = [s for s in STEPS if s in (args.steps or DEFAULT)]
    sink = Local(args.local.resolve(), args.season) if args.local else Database(args.season)
    for kind in (POSTSEASON if args.postseason else [REGULAR]):
        sink.kind = kind
        print(f"{args.season} {kind} -> {'local files in ' + str(sink.folder) if args.local else 'the database'}; steps: {' '.join(steps)}", flush=True)
        for step in steps:
            started = time.perf_counter()
            RUN[step](args.season, sink)
            print(f"  {step} done in {time.perf_counter() - started:.0f}s; size now {sink.size()}", flush=True)


if __name__ == "__main__":
    main()
