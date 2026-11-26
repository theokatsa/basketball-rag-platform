"""Runs a StatQuery over the season tables: the calculation behind a question read by a language model,
or edited by a person on the Scout page.

Nothing in the query is trusted. Names are matched against the database, statistics against the metric
tables, and what cannot be calculated raises QueryError with the reason in plain words. Minimums follow
the NBA.com leaderboards (58 games; FG% 300 made, 3P% 82 made, FT% 125 made), scaled to a slice of the
season, unless the query states its own minimum of games, minutes or attempts.
"""

from __future__ import annotations

import difflib
import operator

import numpy as np
import pandas as pd

from app.services import league_data as data
from app.services.metrics import PLAYER_BY_KEY, TEAM_BY_KEY, Metric
from app.services.query_planner import PLAYER_ALIASES, base_name, find_players, find_teams
from app.services.question_reader import SEASON_MONTHS, Fact, Query, slice_games, sum_players, sum_teams
from app.services.stat_query import Measure, StatQuery

MONTHS = {1: "January", 2: "February", 3: "March", 4: "April", 10: "October", 11: "November", 12: "December"}
OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
OP_WORDS = {">=": "at least", ">": "more than", "<=": "at most", "<": "less than", "==": "exactly"}
STATED = {"games", "minutes", "fga", "fgm", "tpa", "tpm", "fta", "ftm"}  # a stated total on these replaces the default minimums
MADE = {"fg_pct": ("fgm", 300, "field goals made"), "three_pct": ("tpm", 82, "threes made"), "ft_pct": ("ftm", 125, "free throws made")}
NO_MINIMUM = {"height", "weight", "age", "experience", "games", "double_doubles", "triple_doubles", "overall_score", "offense_score", "defense_score"}
COUNTS = {"double_doubles", "triple_doubles"}  # their value is already a count, not an average
GAMES_MINIMUM, LISTED, NEXT = 58, 60, 4


class QueryError(ValueError):
    """The query cannot be run as it stands. The message says why, in words for the page.
    unknown_name: a player or team that is not in the season, a reason to decline rather than to try again."""

    def __init__(self, message: str, unknown_name: bool = False):
        super().__init__(message)
        self.unknown_name = unknown_name


# ------------------------------------------------------------------ names, statistics, words

def _same_person(asked: str, found: str) -> bool:
    """find_players forgives a lot ("Michael" alone finds a Michael); a name from a reader must match by surname."""
    asked = PLAYER_ALIASES.get(asked.strip().lower(), asked)
    a, f = base_name(asked).split(), base_name(found).split()
    if not a or not f:
        return False
    if len(a) == 1:
        return a[0] in f or bool(difflib.get_close_matches(a[0], f, n=1, cutoff=0.84))
    return a[-1] == f[-1] or difflib.SequenceMatcher(None, " ".join(a), " ".join(f)).ratio() >= 0.8


def _players(db, names: list[str]) -> list[dict]:
    folk = data.people(db)[["player_id", "full_name", "points"]].to_dict("records")
    found = []
    for name in names:
        match = find_players(name, folk, limit=1)
        if not match or not _same_person(name, match[0]["full_name"]):
            raise QueryError(f"No player called {name} played in {data.season_name(db)}.", unknown_name=True)
        found.append(match[0])
    return list({p["player_id"]: p for p in found}.values())


def _teams(db, names: list[str]) -> list[dict]:
    records = data.team_list(db).to_dict("records")
    found = []
    for name in names:
        match = find_teams(name, records)[0] or find_teams(name.title(), records)[0]
        if not match:
            raise QueryError(f"There is no NBA team called {name}.", unknown_name=True)
        found.append(match[0])
    return list({t["nba_team_id"]: t for t in found}.values())


def _metric(stat: str, entity: str) -> Metric:
    table = PLAYER_BY_KEY if entity == "player" else TEAM_BY_KEY
    if stat not in table:
        raise QueryError(f"“{stat.replace('_', ' ')}” is not kept for {entity}s.")
    return table[stat]


def _unit(metric: Metric, single: bool = False) -> str:
    unit = metric.unit or metric.label.lower()
    return unit[:-1] if single and unit.endswith("s") and not unit.endswith("ss") else unit


def _label(metric: Metric, extra: list[Metric], basis: str) -> str:
    names = " + ".join(_unit(p) for p in [metric, *extra])
    if metric.total is None or metric.key in COUNTS:
        return names if extra or metric.key in COUNTS else metric.label.lower()
    return {"per_game": f"{names} per game", "total": f"total {names}", "per_36": f"{names} per 36 minutes"}[basis]


def _condition_words(c, entity: str) -> str:
    metric = _metric(c.stat, entity)
    if metric.key in COUNTS and c.basis == "in_game" and c.op in (">=", ">") and c.value <= 1:
        return "a " + metric.label.lower()[:-1]  # "a triple-double"
    if c.basis == "in_game":
        return f"{OP_WORDS[c.op]} {metric.show(c.value) if metric.key == 'height' else f'{c.value:g}'} {_unit(metric)} in the game"
    value = metric.show(c.value) if metric.key in ("height", "weight") else f"{c.value:g}{metric.suffix}"
    label = metric.label.lower() if metric.total is None or c.basis not in ("per_game", "total") or metric.key in COUNTS else _label(metric, [], c.basis)
    return f"{OP_WORDS[c.op]} {value} {label}"


def _clean(values) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _values(frame: pd.DataFrame, metric: Metric, basis: str, entity: str) -> pd.Series:
    if basis == "total" and metric.total is not None:
        out = metric.total(frame)
    elif basis == "per_36" and metric.total is not None and entity == "player":
        out = metric.total(frame) * 36 / frame["minutes"]
    else:
        out = metric.value(frame)
    return _clean(pd.Series(out, index=frame.index))


class Calculated:
    """A measure over a frame, with the words and number format that go with it."""

    def __init__(self, frame: pd.DataFrame, m: Measure, entity: str, in_game: bool = False):
        self.metric = _metric(m.stat, entity)
        extra = [_metric(k, entity) for k in m.plus]
        self.ratio = m.divide_by is not None
        basis = "per_game" if in_game else m.basis
        if self.ratio:
            bottom = _metric(m.divide_by, entity)
            if any(p.total is None for p in [self.metric, *extra, bottom]):
                raise QueryError("A ratio is made from counting statistics, such as blocks and fouls.")
            top = sum(p.total(frame) for p in [self.metric, *extra])
            self.values = _clean(m.multiply * top / bottom.total(frame))
            share = "%" if m.multiply == 100 else ""
            self.label = f"{' + '.join(_unit(p) for p in [self.metric, *extra])} per {_unit(bottom, single=True)}" + (" (%)" if share else "")
            self.digits, self.suffix = (1, "%") if share else (2, "")
        else:
            values = _values(frame, self.metric, basis, entity)
            for p in extra:
                values = values + _values(frame, p, basis, entity)
            self.values = values * m.multiply if m.multiply != 1 else values
            self.label = _label(self.metric, extra, basis) if not in_game else " + ".join(_unit(p) for p in [self.metric, *extra])
            whole = in_game and self.metric.total is not None or (basis == "total" and self.metric.total is not None) or self.metric.key in COUNTS
            self.digits, self.suffix = (0, "") if whole else (self.metric.digits, self.metric.suffix)
        self.uses = [(self.metric, basis), *[(p, basis) for p in extra]] + ([(self.metric, "rate")] if self.ratio else [])

    def show(self, value, at_least: int = 0) -> str:
        if value is None or pd.isna(value):
            return "no data"
        if self.metric.key == "height" and not self.ratio:
            return self.metric.show(value)
        return f"{value:{'+' if self.metric.signed and not self.ratio else ''}.{max(self.digits, at_least)}f}{self.suffix}"


# ------------------------------------------------------------------ the frames

def _slice(db, s: StatQuery) -> Query:
    q = Query(text="")
    q.opponents = _teams(db, s.opponents) if s.opponents else []
    q.home, q.won, q.last = s.home, s.won, s.last_games
    if s.months:
        q.months = {m for m in s.months if m in MONTHS}
        if not q.months:
            raise QueryError("The regular season runs from October to April.")
    words = {True: "at home", False: "on the road"}.get(s.home, ""), {True: "in wins", False: "in losses"}.get(s.won, "")
    q.scope = [w for w in words if w]
    if q.months:
        q.scope.append("in " + " and ".join(MONTHS[m] for m in sorted(q.months, key=SEASON_MONTHS.index)))
    if q.last:
        q.scope.append(f"in the last {q.last} games")
    if q.opponents:
        q.scope.append("against the " + " and ".join(t["full_name"] for t in q.opponents))
    return q


def _group(db, s: StatQuery, frame: pd.DataFrame, team_column: str) -> tuple[pd.DataFrame, list[str]]:
    words = []
    if s.entity == "player":
        on = _teams(db, s.on_teams or ([] if s.players else s.teams))
        if on:
            frame = frame[frame[team_column].isin([t["nba_team_id"] for t in on])]
            words.append("on the " + " and ".join(t["full_name"] for t in on))
        if s.positions:
            frame = frame[[any(p in str(pos) for p in s.positions) for pos in frame["position"]]]
            words.insert(0, " and ".join(p.lower() + "s" for p in s.positions))
        if s.rookies:
            frame = frame[frame["experience"] == 1]
            words.insert(0, "rookies")
    if s.conference:
        conference = frame[team_column].map(data.team_list(db)["conference"]) if team_column in frame else frame["conference"]
        frame = frame[conference == s.conference]
        words.append(f"in the {s.conference}ern Conference")
    return frame, words


def _season_frame(db, s: StatQuery, q: Query) -> pd.DataFrame:
    return sum_players(db, q) if s.entity == "player" else sum_teams(db, q).assign(team=lambda f: f.index)


def _game_rows(db, s: StatQuery, q: Query) -> pd.DataFrame:
    if s.entity == "player":
        rows = slice_games(data.box_scores(db), q, "player_id")
        people = data.people(db)[["full_name", "position", "experience", "age", "inches", "weight"]]
        rows = rows.join(people, on="player_id", how="inner")
    else:
        rows = slice_games(data.team_games(db), q, "team")
        rows = rows.join(data.team_list(db)[["full_name"]], on="team")
    return rows.assign(gp=1)


def _filter(frame: pd.DataFrame, s: StatQuery, conditions, entity: str) -> pd.DataFrame:
    for c in conditions:
        metric = _metric(c.stat, entity)
        values = _values(frame, metric, "per_game" if c.basis == "in_game" else c.basis, entity)
        frame = frame[OPS[c.op](values, c.value).fillna(False)]
    return frame


def _minimums(frame: pd.DataFrame, s: StatQuery, uses: list[tuple[Metric, str]], part: float) -> tuple[pd.DataFrame, list[str]]:
    """NBA.com leaderboard minimums for rates and averages, unless the query states a minimum itself."""
    if s.entity != "player" or any(c.stat in STATED and c.basis != "per_game" for c in s.conditions):
        return frame, []
    uses = uses + [(_metric(c.stat, "player"), c.basis) for c in s.conditions if c.basis != "in_game"]
    notes, games = [], False
    for metric, basis in uses:
        if metric.key in MADE:
            column, least, words = MADE[metric.key]
            frame = frame[frame[column] >= round(least * part)]
            notes.append(f"at least {round(least * part)} {words}")
        elif metric.key in NO_MINIMUM or (basis == "total" and metric.total is not None):
            continue
        else:
            games = True
    if games:
        frame = frame[frame["gp"] >= max(1, round(GAMES_MINIMUM * part))]
        notes.insert(0, f"at least {max(1, round(GAMES_MINIMUM * part))} games")
    return frame, list(dict.fromkeys(notes))


# ------------------------------------------------------------------ answers

def _who(entity: str, group: list[str]) -> str:
    """"guards on the Lakers", "rookies", "players in the Western Conference"."""
    if entity == "team":
        return " ".join(["teams", *group])
    if group and (group[0] == "rookies" or group[0].endswith(("guards", "forwards", "centers"))):
        return " ".join(group)
    return " ".join(["players", *group])


def _name(frame: pd.DataFrame, key) -> str:
    return str(frame.loc[key, "full_name"])


def _ordered(values: pd.Series, frame: pd.DataFrame, highest: bool) -> pd.Series:
    minutes = frame["minutes"].reindex(values.index) if "minutes" in frame else pd.Series(0, index=values.index)
    order = pd.DataFrame({"v": values, "m": minutes}).dropna(subset=["v"]).sort_values(["v", "m"], ascending=[not highest, False])
    return order["v"]


def _describe(s: StatQuery, q: Query, group: list[str], measure: str | None, notes: list[str], subjects: list[str]) -> list[str]:
    steps = [("Players" if s.entity == "player" else "Teams") + (": " + ", ".join(subjects) if subjects else "")]
    if group:
        steps.append("Group: " + ", ".join(group))
    if q.scope:
        steps.append("Games: " + ", ".join(q.scope))
    for c in s.conditions:
        steps.append("Condition: " + _condition_words(c, s.entity))
    if measure:
        steps.append("Measure: " + measure)
    steps.append({
        "rank": f"{'Highest' if s.order == 'highest' else 'Lowest'} first, top {s.limit}", "value": "The value for each one named",
        "compare": "Side by side", "count": "Counted", "average": "Averaged over everyone who qualifies", "sum": "Added up over everyone who qualifies",
        "list": "Everyone who qualifies",
    }[s.operation])
    if notes:
        steps.append("Minimum (NBA.com leaderboards): " + ", ".join(notes))
    return steps


def run(db, s: StatQuery) -> Fact:
    if not s.answerable:
        raise QueryError("This question is outside the 2024-25 regular-season statistics.")
    if s.topic == "other":
        raise QueryError("This kind of question is answered by the rule reader.")
    q = _slice(db, s)
    if s.topic == "season":
        return _season(db, s, q)
    return _games(db, s, q)


def _subjects(db, s: StatQuery) -> list[dict]:
    if s.entity == "player":
        return _players(db, s.players)
    return _teams(db, s.teams)


def _season(db, s: StatQuery, q: Query) -> Fact:
    entity = s.entity
    frame = _season_frame(db, s, q)
    subjects = _subjects(db, s)
    ids = [p["player_id"] if entity == "player" else p["nba_team_id"] for p in subjects]
    names = [p["full_name"] for p in subjects]
    part = min(1.0, float(frame["gp"].max()) / 82) if len(frame) else 1.0
    measure = Calculated(frame, s.measure, entity) if s.measure else None
    if measure and q.sliced and measure.metric.season_only:
        raise QueryError(f"{measure.metric.label} is kept for the whole season only, not for games {', '.join(q.scope)}.")
    where = f" {' '.join(q.scope)}" if q.scope else ""

    if s.operation in ("value", "compare") or (ids and s.operation == "rank"):
        if not ids:
            raise QueryError("Name the players or teams to look up.")
        if not measure:
            raise QueryError("Say which statistic to look up.")
        values = measure.values.reindex(ids)
        if entity == "team" and measure.metric.key in ("wins", "losses"):
            parts = [f"the {n} were {int(frame.loc[i, 'won'])}-{int(frame.loc[i, 'gp'] - frame.loc[i, 'won'])}{where}" if i in frame.index else f"the {n} played no such games" for i, n in zip(ids, names)]
            answer = "; ".join(parts) + "."
            answer = answer[0].upper() + answer[1:]
        else:
            parts = [f"{n} {measure.show(values.get(i))} {measure.label}" if i in frame.index else f"{n} played no such games" for i, n in zip(ids, names)]
            answer = ("; ".join(parts) if len(parts) > 1 else parts[0]) + f"{where}."
            if len(ids) > 1 and values.notna().sum() > 1:
                high = values.idxmax() if s.order == "highest" else values.idxmin()
                answer += f" {names[ids.index(high)]} is {'higher' if s.order == 'highest' else 'lower'}."
        table = {"columns": ["Player" if entity == "player" else "Team", measure.label], "rows": [[n, measure.show(values.get(i))] for i, n in zip(ids, names)]}
        return Fact(f"{' and '.join(names)}: {measure.label}{where}", answer, "", f"{entity}:{ids[0]}" if len(ids) == 1 else "league",
                    ids if entity == "player" else [], ids if entity == "team" else [], table, _describe(s, q, [], measure.label, [], names))

    frame, group = _group(db, s, frame, "team")
    frame = _filter(frame, s, s.conditions, entity)
    frame, notes = _minimums(frame, s, measure.uses if measure else [], part)
    group_words = " ".join(group)
    conditions = " and ".join(_condition_words(c, entity) for c in s.conditions)
    who = _who(entity, group)
    detail = ("Qualified: " + ", ".join(notes) + " (NBA.com leaderboard rule).") if notes else ""
    plan = _describe(s, q, group, measure.label if measure else None, notes, [])
    if not len(frame):
        return Fact(f"{who} {conditions}".strip(), f"No {who} {('with ' + conditions) if conditions else 'qualify'}{where}.", detail, plan=plan)

    if s.operation in ("count", "list") or not measure:
        values = measure.values.reindex(frame.index) if measure else (_values(frame, _metric(s.conditions[0].stat, entity), s.conditions[0].basis, entity) if s.conditions else frame["gp"])
        order = _ordered(values, frame, s.order == "highest")
        listed = [_name(frame, i) for i in order.index[:LISTED]]
        more = f" and {len(order) - LISTED} more" if len(order) > LISTED else ""
        label = measure.label if measure else (_condition_words(s.conditions[0], entity).split(" ", 2)[-1] if s.conditions else "games")
        lead = f"{len(order)} {who}{' with ' + conditions if conditions else ''}{where}"
        answer = f"{lead}: {', '.join(listed)}{more}." if s.operation == "count" else f"{', '.join(listed)}{more} ({lead})."
        table = {"columns": ["#", "Player" if entity == "player" else "Team", label], "rows": [[k, _name(frame, i), measure.show(v) if measure else f"{v:g}"] for k, (i, v) in enumerate(order.head(LISTED).items(), 1)]}
        return Fact(f"{who} {conditions}{where}".strip(), answer, detail, "league", [int(i) for i in order.index[:12]] if entity == "player" else [], [int(i) for i in order.index[:12]] if entity == "team" else [], table, plan)

    values = measure.values.reindex(frame.index)
    if s.operation in ("average", "sum"):
        valid = values.dropna()
        total = valid.mean() if s.operation == "average" else valid.sum()
        what = "average" if s.operation == "average" else "total"
        answer = f"The {what} {measure.label} of the {len(valid)} {who}{' with ' + conditions if conditions else ''}{where} is {measure.show(total, at_least=1 if what == 'average' else 0)}."
        return Fact(f"{what.title()} {measure.label}", answer, detail, "league", [int(i) for i in valid.index[:12]] if entity == "player" else [], [], None, plan)

    order = _ordered(values, frame, s.order == "highest")
    if not len(order):
        return Fact(f"{who} by {measure.label}", f"No {who} have a {measure.label}{where}.", detail, plan=plan)
    side = "highest" if s.order == "highest" else "lowest"
    among = f" among {who}" if group_words or conditions else ""
    among += f" with {conditions}" if conditions else ""
    shown = order.head(max(s.limit, 1 + NEXT if s.limit == 1 else s.limit))
    if s.limit == 1:
        tied = [i for i, v in order.items() if v == order.iloc[0]]
        answer = f"{' and '.join(_name(frame, i) for i in tied)} with {measure.show(order.iloc[0])} {measure.label}{where}, the {side}{among}."
        rest = [i for i in shown.index if i not in tied]
        if rest:
            answer += " Next: " + ", ".join(f"{_name(frame, i)} {measure.show(order[i])}" for i in rest) + "."
    else:
        answer = f"The {side} {measure.label}{where}{among}: " + ", ".join(f"{k}. {_name(frame, i)} {measure.show(v)}" for k, (i, v) in enumerate(order.head(s.limit).items(), 1)) + "."
    table = {"columns": ["#", "Player" if entity == "player" else "Team", measure.label], "rows": [[k, _name(frame, i), measure.show(v)] for k, (i, v) in enumerate(shown.items(), 1)]}
    ids_out = [int(i) for i in shown.index]
    return Fact(f"{who.title()} by {measure.label}{where}", answer, detail, "league", ids_out if entity == "player" else [], ids_out if entity == "team" else [], table, plan)


def _games(db, s: StatQuery, q: Query) -> Fact:
    entity = s.entity
    key = "player_id" if entity == "player" else "team"
    rows = _game_rows(db, s, q)
    subjects = _subjects(db, s)
    ids = [p["player_id"] if entity == "player" else p["nba_team_id"] for p in subjects]
    names = [p["full_name"] for p in subjects]
    rows, group = _group(db, s, rows, "team")
    in_game = [c for c in s.conditions if c.basis == "in_game"]
    season = [c for c in s.conditions if c.basis != "in_game"]
    if season:  # "players averaging 20 points": judged on the whole season
        whole = _filter(_season_frame(db, s, Query(text="")), s, season, entity)
        rows = rows[rows[key].isin(whole.index)]
    rows = _filter(rows, s, in_game, entity)
    if ids:
        rows = rows[rows[key].isin(ids)]
    where = f" {' '.join(q.scope)}" if q.scope else ""
    group_words = " ".join(group)
    teams = data.team_list(db)["full_name"]
    plan_measure = None

    if s.topic == "game_count":
        conditions = " and ".join(_condition_words(c, entity) for c in s.conditions) or "any condition"
        counts = rows.groupby(key).size()
        plan = _describe(s, q, group, "games that meet the conditions", [], names)
        if s.operation in ("value", "compare") or ids:
            values = [int(counts.get(i, 0)) for i in ids]
            answer = "; ".join(f"{n} had {v} {'game' if v == 1 else 'games'} with {conditions}" for n, v in zip(names, values)) + f"{where}."
            return Fact(f"Games with {conditions}", answer, "", f"{entity}:{ids[0]}" if len(ids) == 1 else "league", ids if entity == "player" else [], ids if entity == "team" else [],
                        {"columns": ["Player" if entity == "player" else "Team", "Games"], "rows": [[n, v] for n, v in zip(names, values)]}, plan)
        top = counts.sort_values(ascending=s.order == "lowest")
        label = lambda i: rows.loc[rows[key] == i, "full_name"].iloc[0]  # noqa: E731
        who = _who(entity, group)
        if not len(top):
            return Fact(f"Games with {conditions}", f"No {who} had a game with {conditions}{where}.", "", plan=plan)
        if s.operation == "count":
            answer = f"There were {len(rows)} games with {conditions}{where}, by {len(top)} {who}. Most: " + ", ".join(f"{label(i)} {v}" for i, v in top.head(5).items()) + "."
        elif s.operation == "list":
            answer = ", ".join(f"{label(i)} ({v})" for i, v in top.head(LISTED).items()) + f": {who} with games of {conditions}{where}."
        else:
            first = top.iloc[0]
            tied = [i for i, v in top.items() if v == first]
            answer = f"{' and '.join(label(i) for i in tied)}: {first} {'game' if first == 1 else 'games'} with {conditions}{where}, the most." if s.order == "highest" else f"{' and '.join(label(i) for i in tied)}: {first} such games."
            rest = [i for i in top.index[: len(tied) + NEXT] if i not in tied]
            if rest:
                answer += " Next: " + ", ".join(f"{label(i)} {top[i]}" for i in rest) + "."
        table = {"columns": ["#", "Player" if entity == "player" else "Team", "Games"], "rows": [[k, label(i), int(v)] for k, (i, v) in enumerate(top.head(15).items(), 1)]}
        listed = [int(i) for i in top.index[:12]]
        return Fact(f"Most games with {conditions}", answer, "", "league", listed if entity == "player" else [], listed if entity == "team" else [], table, plan)

    if not s.measure:
        raise QueryError("Say which statistic decides the best game.")
    measure = Calculated(rows, s.measure, entity, in_game=True)
    if measure.metric.season_only:
        raise QueryError(f"{measure.metric.label} is kept for the whole season, not for single games.")
    plan_measure = measure.label
    order = _ordered(measure.values, rows, s.order == "highest")
    plan = _describe(s, q, group, plan_measure, [], names)
    if not len(order):
        return Fact(f"Games by {measure.label}", f"No game{where} matches.", "", plan=plan)
    if ids:  # each one's best game
        best = [order[rows.loc[order.index, key] == i].head(1) for i in ids]
        order = pd.concat([b for b in best if len(b)]) if any(len(b) for b in best) else order.head(0)
        if not len(order):
            return Fact(f"Games by {measure.label}", f"{' and '.join(names)} played no such games{where}.", "", plan=plan)

    def game(i) -> str:
        r = rows.loc[i]
        date = pd.Timestamp(r["game_date"])
        return f"{r['full_name']} {measure.show(order[i])} {measure.label} {'at home ' if r['home'] else ''}against the {teams.get(r['opp'], 'opponent')} on {date.day} {date.strftime('%B %Y')}"

    side = "highest" if s.order == "highest" else "lowest"
    head = order.head(max(s.limit, 1 + NEXT if s.limit == 1 else s.limit))
    if ids or s.limit > 1:
        answer = "; ".join(game(i) for i in order.head(max(s.limit, len(ids))).index) + "."
    else:
        answer = f"{game(head.index[0])}, the {side} in a game{where}" + (f" by {group_words}" if group_words else "") + "."
        if len(head) > 1:
            answer += " Next: " + "; ".join(game(i) for i in head.index[1:]) + "."
    answer = answer[0].upper() + answer[1:]
    table = {"columns": ["#", "Player" if entity == "player" else "Team", "Opponent", "Date", measure.label],
             "rows": [[k, rows.loc[i, "full_name"], teams.get(rows.loc[i, "opp"], ""), str(pd.Timestamp(rows.loc[i, "game_date"]).date()), measure.show(v)] for k, (i, v) in enumerate(head.items(), 1)]}
    listed = [int(rows.loc[i, key]) for i in head.index]
    return Fact(f"Games by {measure.label}{where}", answer, "", "league", listed if entity == "player" else [], listed if entity == "team" else [], table, plan)
