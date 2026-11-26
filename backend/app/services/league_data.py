"""The season as in-memory tables, for calculations over any slice of it.

box     one row per player and game          (about 26,000)
teams   one row per team and game, with the opponent's line as a_*
people  one row per player: team, position, size, age, advanced statistics, scores
shots   shots grouped by player, zone and shot type
Loaded once and cached; an ingest script run needs a restart or half an hour.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from app.services.cache import cached, rows
from app.services.game_service import EAST
from app.services.insight_service import inches, load_profiles
from app.services.shot_service import OPPONENT_SQL, ZONE_SQL
from app.core.config import ACTIVE_SEASON_SQL

SUMS = ["minutes", "points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf"]
SEASON = ACTIVE_SEASON_SQL


def _frame(db, sql, params=None) -> pd.DataFrame:
    return pd.DataFrame(rows(db, text(sql), params))


def team_list(db) -> pd.DataFrame:
    def load():
        frame = _frame(db, "select nba_team_id, full_name, city, nickname, abbreviation, year_founded from teams")
        frame["conference"] = ["East" if a in EAST else "West" for a in frame["abbreviation"]]
        return frame.set_index("nba_team_id", drop=False)

    return cached("frame_team_list", load)


def team_games(db) -> pd.DataFrame:
    def load():
        frame = _frame(db, f"""select nba_game_id as game_id, game_date, nba_team_id as team, opponent_nba_team_id as opp, is_home as home, won,
            {', '.join(SUMS)} from team_box_scores where season = {SEASON} order by game_date, nba_game_id""")
        other = frame[["game_id", "team", *SUMS]].rename(columns={"team": "opp", **{c: f"a_{c}" for c in SUMS}})
        frame = frame.merge(other, on=["game_id", "opp"])
        periods = _frame(db, f"select nba_game_id as game_id, nba_team_id as team, period, points from team_period_scores where season = {SEASON}")
        wide = periods.pivot_table(index=["game_id", "team"], columns="period", values="points")
        wide.columns = [f"q{c}" for c in wide.columns]
        frame = frame.merge(wide.reset_index(), on=["game_id", "team"], how="left")
        allowed = wide.reset_index().rename(columns={"team": "opp", **{c: f"a_{c}" for c in wide.columns}})
        frame = frame.merge(allowed, on=["game_id", "opp"], how="left")
        frame["margin"] = frame["points"] - frame["a_points"]
        frame["overtime"] = frame["q5"].notna() if "q5" in frame else False
        frame["game_date"] = pd.to_datetime(frame["game_date"])
        return frame.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    return cached("frame_team_games", load)


def box_scores(db) -> pd.DataFrame:
    def load():
        frame = _frame(db, f"select nba_game_id as game_id, player_id, nba_team_id as team, {', '.join(SUMS)}, plus_minus from player_box_scores where season = {SEASON}")
        games = team_games(db)[["game_id", "team", "opp", "home", "won", "margin", "overtime", "game_date"]]
        frame = frame.merge(games, on=["game_id", "team"])
        tens = sum((frame[c] >= 10).astype(int) for c in ("points", "reb", "ast", "stl", "blk"))
        frame["double_doubles"], frame["triple_doubles"] = (tens >= 2).astype(int), (tens >= 3).astype(int)
        frame["game_score"] = (
            frame.points + 0.4 * frame.fgm - 0.7 * frame.fga - 0.4 * (frame.fta - frame.ftm) + 0.7 * frame.oreb + 0.3 * frame.dreb
            + frame.stl + 0.7 * frame.ast + 0.7 * frame.blk - 0.4 * frame.pf - frame.tov
        )
        return frame.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    return cached("frame_box", load)


def people(db) -> pd.DataFrame:
    def load():
        frame = _frame(db, f"""
            select p.id as player_id, p.full_name, p.is_active, pp.position, pp.height, pp.weight, pp.season as career, t.nba_team_id as team, s.games_played as gp, s.minutes as mpg, s.points,
                   a.season_age as age, a.ast_pct, a.ast_to, a.oreb_pct, a.dreb_pct, a.reb_pct, a.tov_pct, a.efg_pct, a.usg_pct, a.off_rating, a.def_rating, a.net_rating, a.pie, a.pace, a.possessions,
                   a.defended_fga, a.defended_fg_pct, a.defended_fg_diff
            from player_season_stats s join players p on p.id = s.player_id
            left join player_profiles pp on pp.player_id = p.id left join teams t on t.id = s.team_id
            left join player_advanced_stats a on a.player_id = p.id and a.season = s.season
            where s.season = {SEASON}""")
        frame["inches"] = [inches(h) for h in frame["height"]]
        frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
        # "2018-25" is the first and last season on record, so the first year gives experience.
        frame["experience"] = int(str(_frame(db, f"select {SEASON} as s").s[0])[:4]) - pd.to_numeric(frame["career"].str[:4], errors="coerce") + 1
        scores = load_profiles(db)
        for source, column in (("score", "overall_score"), ("offense_score", "offense_score"), ("defense_score", "defense_score")):
            frame[column] = [scores[i][source] if i in scores else None for i in frame["player_id"]]
        for column in ("ast_pct", "oreb_pct", "dreb_pct", "reb_pct", "efg_pct", "usg_pct", "pie", "defended_fg_pct", "defended_fg_diff"):
            frame[column] = frame[column] * 100
        frame["position"] = frame["position"].fillna("")
        frame["conference"] = frame["team"].map(team_list(db)["conference"])
        return frame.set_index("player_id", drop=False)

    return cached("frame_people", load)


def shots(db, opponent: str | None = None) -> pd.DataFrame:
    """opponent: a team abbreviation, to keep only shots against it."""
    def load():
        condition = f"and {OPPONENT_SQL} = :opponent" if opponent else ""
        return _frame(db, f"""
            select sc.player_id, t.nba_team_id as team, {ZONE_SQL} as zone, sc.shot_zone_basic as basic, sc.action_type as action, sc.shot_type like '3%' as three, sc.period,
                   count(*) as tries, sum(sc.shot_made::int) as made, sum(sc.shot_distance) as feet
            from shot_charts sc join teams t on t.id = sc.team_id where sc.season = {SEASON} {condition} group by 1, 2, 3, 4, 5, 6, 7""", {"opponent": opponent} if opponent else {})

    return cached(("frame_shots", opponent), load)


def season_name(db) -> str:
    return cached("season_name", lambda: rows(db, text(f"select {SEASON} as s"))[0]["s"])


def warm(db) -> None:
    for load in (team_list, team_games, box_scores, people, shots):
        load(db)
