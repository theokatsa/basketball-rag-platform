"""Exact answers by calculation: subject + metric + slice of games + operation.

Retrieval finds text that was written in advance. Most questions about statistics ask for a
number nobody wrote down ("points at home in January", "most 40-point games"), so this module
reads the question into a small structure and calculates over the tables of league_data.
A result is returned as evidence, like a retrieved document, with the method spelled out.

question_reader.py reads the question, team_facts.py holds the calculations about teams,
shots, pairs and lineups; this file holds those about players and chooses between them.
"""

from __future__ import annotations

import re
from dataclasses import replace

import numpy as np
import pandas as pd

from app.services import audience_service, team_style
from app.services import league_data as data
from app.services import team_facts as tf
from app.services.metrics import PLAYER_BY_KEY, Metric
from app.services.query_planner import has
from app.services.question_reader import LEAST, MOST, SINGLE, SUPERLATIVE, TOP, Fact, Query, describe_plan, descending, eligible, group_words, ids_of, parse, slice_games, sum_players, wants_total, where_words

__all__ = ["Fact", "Query", "answer", "parse"]

NAMES = {"points": "points", "reb": "rebounds", "ast": "assists", "stl": "steals", "blk": "blocks", "tpm": "threes", "tov": "turnovers"}
COMPARISONS = {">=": "at least", ">": "more than", "<": "fewer than", "<=": "at most", "==": "exactly"}
SUM_COLUMNS = [*data.SUMS, "plus_minus", "game_score", "double_doubles", "triple_doubles"]
COUNTED = ("double_doubles", "triple_doubles", "games")


def _test(values, op, limit):
    return {">=": values >= limit, ">": values > limit, "<": values < limit, "<=": values <= limit, "==": values == limit}[op]


def _label(metric: Metric, as_total: bool) -> str:
    if as_total or metric.key in COUNTED:
        return f"total {metric.unit or metric.label.lower()}"
    if metric.total is not None and metric.unit:
        return f"{metric.unit} per game"
    return metric.label.lower()


def _value(metric: Metric, as_total: bool):
    return metric.total if as_total else metric.value


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _split(metric: Metric, row) -> str:
    pairs = {"three_pct": ("tpm", "tpa"), "ft_pct": ("ftm", "fta"), "fg_pct": ("fgm", "fga")}
    if metric.key not in pairs:
        return ""
    made, tried = pairs[metric.key]
    return f" ({row[made]:.0f} of {row[tried]:.0f})"


def player_value(db, q: Query) -> Fact | None:
    sums = sum_players(db, q)
    lines, table = [], []
    for p in q.players:
        name = p["full_name"]
        if p["player_id"] not in sums.index:
            lines.append(f"{name} played no games{where_words(q)}.")
            continue
        row = sums.loc[p["player_id"]]
        for metric in q.metrics[:4]:
            as_total = wants_total(q, metric)
            value = _value(metric, as_total)(row)
            shown = metric.show(value)
            if metric.season_only and q.sliced:
                lines.append(f"{metric.label} is only recorded for the whole season: {name} had {shown}.")
            elif metric.key == "height":
                lines.append(f"{name} is {shown} tall.")
            elif metric.key == "weight":
                lines.append(f"{name} weighs {shown}.")
            elif metric.key == "age":
                lines.append(f"{name} was {shown} years old in the {data.season_name(db)} season.")
            elif metric.key == "experience":
                lines.append(f"{data.season_name(db)} was season {shown} in the league for {name}.")
            elif metric.key in COUNTED:
                lines.append(f"{name} {'played' if metric.key == 'games' else 'had'} {shown} {metric.unit}{where_words(q)}.")
            elif as_total:
                lines.append(f"{name} had {value:.0f} {metric.unit or metric.label.lower()}{where_words(q)} ({metric.show(metric.value(row))} per game over {row.gp:.0f} games).")
            elif metric.total is not None and metric.unit:
                lines.append(f"{name} averaged {shown} {metric.unit}{where_words(q)} over {row.gp:.0f} games ({metric.total(row):.0f} in total).")
            else:
                lines.append(f"{name}'s {metric.label.lower()}{where_words(q)} was {shown}{_split(metric, row)}.")
            table.append([name, metric.label + (" (total)" if as_total else ""), f"{value:.0f}" if as_total else shown, f"{row.gp:.0f}"])
            if not q.sliced and not as_total and len(q.players) == 1 and metric.key not in ("height", "weight", "age", "experience", *COUNTED):
                pool = eligible(sums, metric, replace(q, roles=[], min_age=None, max_age=None, conference=None, rookies=False))
                if p["player_id"] in pool.index:
                    values = metric.value(pool).astype(float)
                    place = int(((values < value) if metric.lower else (values > value)).sum()) + 1
                    lines.append(f"That ranks number {place} of {len(values)} qualified players{' (lowest first)' if metric.lower else ''}.")
    if not lines:
        return None
    labels = ", ".join(m.label.lower() for m in q.metrics[:4])
    return Fact(
        f"{', '.join(p['full_name'] for p in q.players)}: {labels}{where_words(q)}", " ".join(lines), "", f"player:{q.players[0]['player_id']}", ids_of(q.players),
        table={"columns": ["Player", "Statistic", "Value", "Games"], "rows": table}, plan=describe_plan(q, f"Calculated: {labels}"),
    )


def player_summary(db, q: Query) -> Fact | None:
    """No statistic named, but a slice of games: the basic line for that slice."""
    sums = sum_players(db, q)
    lines, table = [], []
    for p in q.players:
        if p["player_id"] not in sums.index:
            lines.append(f"{p['full_name']} played no games{where_words(q)}.")
            continue
        r = sums.loc[p["player_id"]]
        fg, three = 100 * r.fgm / max(r.fga, 1), 100 * r.tpm / max(r.tpa, 1)
        lines.append(
            f"{p['full_name']}{where_words(q)}: {r.points / r.gp:.1f} points, {r.reb / r.gp:.1f} rebounds and {r.ast / r.gp:.1f} assists in {r.minutes / r.gp:.1f} minutes over {r.gp:.0f} games,"
            f" shooting {fg:.1f}% from the field and {three:.1f}% from three, plus/minus {r.plus_minus / r.gp:+.1f}."
        )
        table.append([p["full_name"], f"{r.gp:.0f}", f"{r.points / r.gp:.1f}", f"{r.reb / r.gp:.1f}", f"{r.ast / r.gp:.1f}", f"{fg:.1f}%", f"{r.plus_minus / r.gp:+.1f}"])
    return Fact(
        f"{', '.join(p['full_name'] for p in q.players)}{where_words(q)}", " ".join(lines), "", f"player:{q.players[0]['player_id']}", ids_of(q.players),
        table={"columns": ["Player", "Games", "PTS", "REB", "AST", "FG%", "+/-"], "rows": table}, plan=describe_plan(q, "Calculated: average line"),
    )


def player_split(db, q: Query) -> Fact | None:
    """"Better at home or away?", "in wins and losses"."""
    if has(r"home", q.low):
        sides = replace(q, home=True, scope=["at home"]), replace(q, home=False, scope=["on the road"])
    else:
        sides = replace(q, home=None, won=True, scope=["in wins"]), replace(q, home=None, won=False, scope=["in losses"])
    metrics = [m for m in q.metrics[:2] if not m.season_only] or [PLAYER_BY_KEY["points"], PLAYER_BY_KEY["ts"]]
    p = q.players[0]
    a, b = (sum_players(db, x) for x in sides)
    if p["player_id"] not in a.index or p["player_id"] not in b.index:
        return None
    names = [x.scope[0] for x in sides]
    parts, table = [], []
    for m in metrics:
        va, vb = m.value(a.loc[p["player_id"]]), m.value(b.loc[p["player_id"]])
        first = va <= vb if m.lower else va >= vb
        parts.append(f"{p['full_name']} was better {names[0] if first else names[1]} in {m.label.lower()}: {m.show(va)} {names[0]} and {m.show(vb)} {names[1]}.")
        table.append([m.label, m.show(va), m.show(vb)])
    return Fact(f"{p['full_name']} {names[0]} and {names[1]}", " ".join(parts), "", f"player:{p['player_id']}", [p["player_id"]], table={"columns": ["Statistic", *names], "rows": table}, plan=describe_plan(replace(q, scope=[]), f"Compared {names[0]} with {names[1]}"))


def player_rank(db, q: Query) -> Fact | None:
    metric, p = q.metrics[0], q.players[0]
    sums = eligible(sum_players(db, q), metric, q)
    if p["player_id"] not in sums.index:
        return player_value(db, q)
    values = metric.value(sums).dropna()
    own = values[p["player_id"]]
    place = int(((values < own) if metric.lower else (values > own)).sum()) + 1
    note = " (lowest first)" if metric.lower else ""
    return Fact(
        f"{p['full_name']}: rank in {metric.label.lower()}", f"{p['full_name']} ranks number {place} of {len(values)} qualified players in {_label(metric, False)}{where_words(q)}{note} with {metric.show(own)}.",
        "", f"player:{p['player_id']}", [p["player_id"]], plan=describe_plan(q, f"Ranked by {metric.label}"),
    )


def player_top(db, q: Query, metric: Metric) -> Fact | None:
    as_total = wants_total(q, metric)
    everyone = sum_players(db, q)
    sums = eligible(everyone, None if as_total else metric, q)
    for op, limit in q.limits:
        sums = sums[_test(_value(metric, as_total)(sums).astype(float), op, limit)]
    if q.limits and not len(sums):
        return Fact(f"Players by {_label(metric, as_total)}", f"No qualified player has a {metric.label.lower()} like that.", "", plan=describe_plan(q, f"Ranked by {metric.label}"))
    if not len(sums):
        sums = eligible(everyone, metric, q, strict=False)
    values = _value(metric, as_total)(sums).astype(float).replace([np.inf, -np.inf], np.nan).dropna() if len(sums) else pd.Series(dtype=float)
    if not len(values):
        return None
    down = descending(q, metric)
    # Equal numbers: the one who played more.
    order = pd.DataFrame({"v": values, "m": sums["minutes"].reindex(values.index)}).sort_values(["v", "m"], ascending=[not down, False])
    best = [(sums.loc[i, "full_name"], f"{r.v:.0f}" if as_total else metric.show(r.v), int(i)) for i, r in order.head(TOP).iterrows()]
    group = f" among {group_words(q)}" if group_words(q) else ""
    side = "highest" if down else "lowest"
    tied = [n for n, v, _ in best if v == best[0][1]]
    if metric.key in ("height", "weight", "age", "experience"):
        kind = {"height": ("tall", "tallest", "shortest"), "weight": ("", "heaviest", "lightest"), "age": ("years old", "oldest", "youngest"), "experience": ("seasons in the league", "most experienced", "least experienced")}[metric.key]
        lead = f"{', '.join(tied)}: {best[0][1]} {kind[0]}".rstrip() + f", the {kind[1] if down else kind[2]}{group}."
    else:
        lead = f"{', '.join(tied)} with {best[0][1]} {_label(metric, as_total)}{where_words(q)}, the {side}{group}."
    if len(best) > len(tied):
        lead += f" Next: {', '.join(f'{n} {v}' for n, v, _ in best[len(tied):])}."
    if as_total or metric.key in (*COUNTED, "height", "weight", "age", "experience"):
        need = ""
    elif metric.need:
        need = f"At least {metric.need[1]} {tf.NEED_WORDS.get(metric.need[0], metric.need[0])} over a full season."
    else:
        need = "At least 20 games and 12 minutes per game over a full season."
    return Fact(
        f"Players by {_label(metric, as_total)}{where_words(q)}{group}", lead, need, "league", [i for *_, i in best],
        table={"columns": ["#", "Player", metric.label + (" (total)" if as_total else "")], "rows": [[k, n, v] for k, (n, v, _) in enumerate(best, 1)]},
        plan=describe_plan(q, f"Ranked by {_label(metric, as_total)}, {side} first"),
    )


def counted_total(db, q: Query) -> Fact:
    """"How many triple-doubles were there?"""
    metric = next(m for m in q.metrics if m.key in COUNTED)
    sums = eligible(sum_players(db, q), None, q, strict=False)
    values = metric.value(sums)
    best = values.sort_values(ascending=False).head(5)
    group = f" by {group_words(q)}" if group_words(q) else ""
    return Fact(f"{metric.label}{where_words(q)}", f"There were {values.sum():.0f} {metric.unit}{group}{where_words(q)}, by {int((values > 0).sum())} players. Most: " + ", ".join(f"{sums.loc[i, 'full_name']} {v:.0f}" for i, v in best.items()) + ".", "", "league", [int(i) for i in best.index], plan=describe_plan(q, f"Counted {metric.unit}"))


def player_record(db, q: Query) -> Fact | None:
    """Wins and losses of the team in games the player played."""
    frame = slice_games(data.box_scores(db), q, "player_id")
    lines = []
    for p in q.players:
        own = frame[frame.player_id == p["player_id"]]
        lines.append(f"{p['full_name']}'s team was {tf.record(own)}{where_words(q)} in games he played." if len(own) else f"{p['full_name']} played no games{where_words(q)}.")
    return Fact(f"{', '.join(p['full_name'] for p in q.players)}: record{where_words(q)}", " ".join(lines).replace("in games he played", "in games with this player"), "", f"player:{q.players[0]['player_id']}", ids_of(q.players), plan=describe_plan(q, "Record in games played"))


def quarter_scoring(db, q: Query) -> Fact | None:
    """Points from field goals by quarter; free throws are not recorded per quarter."""
    columns, name = tf.quarter(q)
    shots = data.shots(db)
    shots = shots[shots.period.isin([int(c[1:]) for c in columns])]
    points = (shots.made * (2 + shots.three.astype(int))).groupby(shots.player_id).sum().sort_values(ascending=False)
    folk, games = data.people(db), data.people(db).gp
    note = "Field goals only: free throws are not recorded per quarter."
    if q.players:
        lines = [f"{p['full_name']} scored {points.get(p['player_id'], 0):.0f} points from field goals in the {name}, {points.get(p['player_id'], 0) / games[p['player_id']]:.1f} per game." for p in q.players]
        return Fact(f"Scoring in the {name}", " ".join(lines), note, f"player:{q.players[0]['player_id']}", ids_of(q.players), plan=describe_plan(q, f"Field goals in the {name}"))
    keep = eligible(folk, None, q, strict=False)
    best = points[points.index.isin(keep.index)].head(TOP)
    lines = [f"{folk.loc[i, 'full_name']} {v:.0f} ({v / games[i]:.1f} per game)" for i, v in best.items()]
    return Fact(f"Scoring in the {name}", f"{lines[0]} points from field goals in the {name}, the most. Next: {', '.join(lines[1:])}.", note, "league", [int(i) for i in best.index], plan=describe_plan(q, f"Field goals in the {name}"))


def player_compare(db, q: Query) -> Fact | None:
    metrics = q.metrics[:3] or [PLAYER_BY_KEY[k] for k in ("points", "rebounds", "assists", "steals", "blocks", "ts", "three_pct", "net_rating", "overall_score")]
    sums = sum_players(db, q)
    sums = sums.loc[[i for i in ids_of(q.players) if i in sums.index]]
    if len(sums) < 2:
        return None
    answer, table = [], []
    wins = dict.fromkeys(sums.index, 0)
    for m in metrics:
        as_total = wants_total(q, m)
        values = _value(m, as_total)(sums).astype(float).dropna()
        if not len(values):
            continue
        down = descending(q, m) if q.metrics else not m.lower
        ordered = values.sort_values(ascending=not down)
        shown = {i: f"{v:.0f}" if as_total else m.show(v) for i, v in ordered.items()}
        wins[ordered.index[0]] += 1
        table.append([m.label, *[shown.get(i, "no data") for i in sums.index]])
        if q.metrics:
            first, *rest = ordered.index
            answer.append(f"{sums.loc[first, 'full_name']}: {shown[first]} {_label(m, as_total)}{where_words(q)}, against " + ", ".join(f"{sums.loc[i, 'full_name']} {shown[i]}" for i in rest) + ".")
    if not q.metrics:
        for i in sums.index:
            answer.append(f"{sums.loc[i, 'full_name']}: " + ", ".join(f"{m.show(m.value(sums.loc[i]))} {_label(m, False)}" for m in metrics[:6]) + ".")
        answer.append("Better numbers in: " + ", ".join(f"{sums.loc[i, 'full_name']} {n}" for i, n in wins.items()) + f" of {len(table)} statistics.")
    return Fact("Comparison: " + ", ".join(sums.full_name), " ".join(answer), "", f"player:{sums.index[0]}", [int(i) for i in sums.index], table={"columns": ["Statistic", *sums.full_name], "rows": table}, plan=describe_plan(q, "Compared: " + ", ".join(m.label for m in metrics)))


SINGLE_COLUMNS = {
    "points": "points", "rebounds": "reb", "assists": "ast", "steals": "stl", "blocks": "blk", "tpm": "tpm", "turnovers": "tov", "minutes": "minutes", "game_score": "game_score",
    "plus_minus": "plus_minus", "ftm": "ftm", "fta": "fta", "fgm": "fgm", "fga": "fga", "tpa": "tpa", "oreb": "oreb", "dreb": "dreb", "fouls": "pf",
}


def player_single_game(db, q: Query) -> Fact | None:
    metric = next((m for m in q.metrics if m.key in SINGLE_COLUMNS), None)
    if metric is None and has(r"best (?:game|performance|night)s?|performances?|performer", q.low):
        metric = PLAYER_BY_KEY["game_score"]
    if metric is None:
        return None
    # "best performer by game score": the named statistic wins over the general word.
    metric = next((m for m in q.metrics if m.key == "game_score"), metric)
    column, unit = SINGLE_COLUMNS[metric.key], (metric.unit or metric.label).lower()
    frame = slice_games(data.box_scores(db), q, "player_id")
    folk, teams = data.people(db), data.team_list(db)
    keep = ids_of(q.players) if q.players else eligible(folk, None, q, strict=False).index
    frame = frame[frame.player_id.isin(keep) & frame.player_id.isin(folk.index)]
    if not len(frame):
        return None
    low = bool(has(r"fewest|lowest|worst|season[- ]?low", q.low))
    best = frame.sort_values([column, "minutes"], ascending=[low, False]).head(5)

    def show(r):
        return f"{r[column]:.1f}" if column == "game_score" else f"{r[column]:.0f}"

    lines = [f"{folk.loc[r.player_id, 'full_name']} {show(r)} {unit} {'vs' if r.home else 'at'} the {teams.loc[r.opp, 'nickname']} on {r.game_date.day} {r.game_date:%B %Y} ({r.points:.0f} points, {r.reb:.0f} rebounds, {r.ast:.0f} assists)" for _, r in best.iterrows()]
    return Fact(
        f"{'Lowest' if low else 'Best'} single games: {unit}{where_words(q)}", f"{lines[0]}.", "Next: " + "; ".join(lines[1:]) + "." if lines[1:] else "", f"player:{best.iloc[0].player_id}", list(dict.fromkeys(int(i) for i in best.player_id)),
        table={"columns": ["Player", "Date", unit.capitalize(), "PTS", "REB", "AST"], "rows": [[folk.loc[r.player_id, "full_name"], f"{r.game_date:%Y-%m-%d}", show(r), int(r.points), int(r.reb), int(r.ast)] for _, r in best.iterrows()]},
        plan=describe_plan(q, f"Single games by {unit}"),
    )


def player_game_count(db, q: Query) -> Fact | None:
    """How many games met a condition, for one player or as a ranking."""
    frame = slice_games(data.box_scores(db), q, "player_id")
    folk = data.people(db)
    words = []
    for column, op, value in q.thresholds:
        frame = frame[_test(frame[column], op, value)]
        words.append(f"{COMPARISONS[op]} {value:.0f} {NAMES[column]}")
    condition = " and ".join(words)
    plan = describe_plan(q, f"Counted games with {condition}")
    if q.players:
        counts = [(p["full_name"], int((frame.player_id == p["player_id"]).sum())) for p in q.players]
        return Fact(f"Games with {condition}", " ".join(f"{n} had {c} games with {condition}{where_words(q)}." for n, c in counts), "", f"player:{q.players[0]['player_id']}", ids_of(q.players), table={"columns": ["Player", "Games"], "rows": [list(c) for c in counts]}, plan=plan)
    keep = eligible(folk, None, q, strict=False)
    counts = frame[frame.player_id.isin(keep.index)].groupby("player_id").size().sort_values(ascending=False)
    if not len(counts):
        return Fact(f"Games with {condition}", f"Nobody had a game with {condition}{where_words(q)}.", "", plan=plan)
    best = [(folk.loc[i, "full_name"], int(n), int(i)) for i, n in counts.head(TOP).items()]
    if has(r"how many (?:players|different)", q.low):
        lead = f"{len(counts)} players had a game with {condition}{where_words(q)}. Most often: {', '.join(f'{n} {c}' for n, c, _ in best)}."
    elif has(r"how many", q.low):
        lead = f"There were {int(counts.sum())} games with {condition}{where_words(q)}, by {len(counts)} players. Most often: {', '.join(f'{n} {c}' for n, c, _ in best)}."
    else:
        lead = f"{best[0][0]} had the most games with {condition}{where_words(q)}: {best[0][1]}. Next: {', '.join(f'{n} {c}' for n, c, _ in best[1:])}."
    return Fact(f"Most games with {condition}", lead, f"{int(counts.sum())} such games by {len(counts)} players.", "league", [i for *_, i in best], table={"columns": ["Player", "Games"], "rows": [[n, c] for n, c, _ in best]}, plan=plan)


def player_list(db, q: Query) -> Fact | None:
    """Players whose averages meet conditions: a list, or a count."""
    sums = eligible(sum_players(db, q), None, q, strict=False)
    sums = sums[sums.gp >= 2] if q.sliced else sums[(sums.gp >= 10) & (sums.minutes / sums.gp >= 8)]
    words = []
    for column, op, value in q.thresholds:
        sums = sums[_test((sums[column] / sums.gp).round(1), op, value)]
        words.append(f"{COMPARISONS[op]} {value:g} {NAMES[column]}")
    for stat, op, value in q.percents:
        made, tried, least = {"three_point_pct": ("tpm", "tpa", 100), "free_throw_pct": ("ftm", "fta", 75), "field_goal_pct": ("fgm", "fga", 200)}[stat]
        sums = sums[(sums[tried] >= least * (0.1 if q.sliced else 1)) & _test((100 * sums[made] / sums[tried]).round(1), op, value)]
        words.append(f"{COMPARISONS[op]} {value:g}% {stat.replace('_pct', '').replace('_', ' ')} shooting")
    condition = " and ".join(words)
    plan = describe_plan(q, f"Averages: {condition}")
    group = f" {group_words(q)}" if group_words(q) else ""
    if not len(sums):
        return Fact(f"Players averaging {condition}", f"No player{group} averaged {condition}{where_words(q)}.", "", plan=plan)
    if q.thresholds:
        column = q.thresholds[0][0]
        ordered, name, mark = sums.assign(v=sums[column] / sums.gp), NAMES[column], ""
    else:
        made, tried = {"three_point_pct": ("tpm", "tpa"), "free_throw_pct": ("ftm", "fta"), "field_goal_pct": ("fgm", "fga")}[q.percents[0][0]]
        ordered, name, mark = sums.assign(v=100 * sums[made] / sums[tried]), "percentage", "%"
    up = bool((q.thresholds or q.percents)[0][1].startswith("<"))
    ordered = ordered.sort_values("v", ascending=up)
    shown = ordered.head(15)
    listed = ", ".join(f"{r.full_name} ({r.v:.1f}{mark})" for _, r in shown.iterrows())
    n = len(ordered)
    if has(r"how many|number of|count", q.low):
        answer = f"{plural(n, 'player')}{group and f' ({group.strip()})'} averaged {condition}{where_words(q)}: {listed}" + (" and others." if n > len(shown) else ".")
    else:
        answer = f"{listed}{' and others' if n > len(shown) else ''} averaged {condition}{where_words(q)}{f' ({group.strip()})' if group else ''}."
    return Fact(
        f"Players averaging {condition}{group}", answer, f"{plural(n, 'player')}, sorted by {name}; at least 10 games and 8 minutes per game.", "league", [int(i) for i in shown.index],
        table={"columns": ["Player", "PTS", "REB", "AST", "Games"], "rows": [[r.full_name, f"{r.points / r.gp:.1f}", f"{r.reb / r.gp:.1f}", f"{r.ast / r.gp:.1f}", int(r.gp)] for _, r in shown.iterrows()]}, plan=plan,
    )


def form_change(db, q: Query) -> Fact | None:
    """Who improved or declined most over the last games, or how one player changed."""
    window = q.last or 10
    metric = next((m for m in q.metrics if not m.season_only), PLAYER_BY_KEY["game_score" if not q.metrics else "points"])
    frame = slice_games(data.box_scores(db), replace(q, last=None), "player_id")
    frame = frame.assign(back=frame.groupby("player_id").cumcount(ascending=False))

    def totals(part):
        sums = part.groupby("player_id")[SUM_COLUMNS].sum().astype(float)
        sums["gp"] = part.groupby("player_id").size()
        return sums

    now, before = totals(frame[frame.back < window]), totals(frame[frame.back >= window])
    folk = eligible(data.people(db), None, q, strict=False)
    both = [i for i in now.index.intersection(before.index[before.gp >= 15]) if i in folk.index and now.loc[i, "minutes"] / now.loc[i, "gp"] >= 12 and (not metric.need or now.loc[i, metric.need[0]] >= 20)]
    if q.players:
        both = [i for i in both if i in ids_of(q.players)]
    if not both:
        return None
    a, b = metric.value(now.loc[both]), metric.value(before.loc[both])
    change = (a - b).dropna()
    worse = bool(has(r"declin\w*|dropped|worse|fell|cold\w*|slump\w*|cool\w*|worst", q.low))
    ordered = change.sort_values(ascending=worse != metric.lower)
    label = metric.label.lower()
    if q.players:
        answer = " ".join(f"In the last {window} games {folk.loc[i, 'full_name']}'s {label} went from {metric.show(b[i])} to {metric.show(a[i])} ({change[i]:+.1f})." for i in ordered.index)
    else:
        first = ordered.index[0]
        answer = f"{folk.loc[first, 'full_name']} {'declined' if worse else 'improved'} most in {label} over the last {window} games: " + "; ".join(f"{folk.loc[i, 'full_name']} {metric.show(b[i])} to {metric.show(a[i])} ({change[i]:+.1f})" for i in ordered.index[:6]) + "."
    return Fact(
        f"Change in {label}, last {window} games", answer, "Compared with the same player's earlier games; at least 12 minutes per game recently.", f"player:{ordered.index[0]}" if q.players else "league", [int(i) for i in ordered.index[:6]],
        table={"columns": ["Player", "Before", f"Last {window}", "Change"], "rows": [[folk.loc[i, "full_name"], metric.show(b[i]), metric.show(a[i]), f"{change[i]:+.1f}"] for i in ordered.index[:6]]}, plan=describe_plan(replace(q, scope=[]), f"Last {window} games against earlier ones: {metric.label}"),
    )


def roster(db, q: Query) -> Fact | None:
    team = (q.roster or q.teams)[0]
    sums = sum_players(db, Query(""))
    squad = eligible(sums, None, replace(q, roster=[team]), strict=False).sort_values("minutes", ascending=False)
    n, group = len(squad), group_words(replace(q, roster=[]))
    answer = f"The {team['full_name']} have {n} {group or 'players'} in the database: " + ", ".join(f"{r.full_name} ({r.points / r.gp:.1f} points)" for _, r in squad.head(15).iterrows()) + (" and others." if n > 15 else ".")
    return Fact(
        f"{team['full_name']} roster", answer, "Sorted by minutes played.", f"team:{team['nba_team_id']}", [int(i) for i in squad.index[:15]], [team["nba_team_id"]],
        table={"columns": ["Player", "Position", "Age", "Games", "PTS"], "rows": [[r.full_name, r.position, int(r.age), int(r.gp), f"{r.points / r.gp:.1f}"] for _, r in squad.head(18).iterrows()]}, plan=describe_plan(q, "Roster"),
    )


# ------------------------------------------------------------------ choosing the calculation

def answer(db, question: str, q: Query | None = None) -> Fact | None:
    """The calculation a question asks for, or None when it is not a question of this kind."""
    q = q or parse(question, db)
    return _about_players(db, q) if q.players else _about_teams_and_groups(db, q)


def unclear(db, question: str) -> bool:
    """A question about players in general that names no statistic."""
    q = parse(question, db)
    return not (q.players or q.teams or q.roster or q.opponents or q.metrics or q.thresholds or tf.shot_words(q)[0] or has(r"teams?|games?|similar|line[- ]?ups?", q.low))


AUDIENCE = r"most[- ](?:viewed|popular|visited|searched|opened|looked[- ]at)|popular\w*|trending|hidden gems?|underrated|overlooked|under the radar|(?:users?|people|fans) (?:who |that )?(?:also )?(?:look\w*|view\w*|open\w*)|also viewed|how many (?:people|users) (?:view|look|open)\w*"


def audience(db, q: Query) -> Fact | None:
    """What people look at on this site."""
    folk = data.people(db)
    about = audience_service.info(db)
    note = f"Counted from {about['users']} accounts on this site" + (f", {about['simulated']} of them simulated." if about["simulated"] else ".")

    def name(i):
        return folk.at[i, "full_name"] if i in folk.index else "Unknown player"

    if q.players:
        p = q.players[0]
        if has(r"also", q.low):
            found = audience_service.also_viewed(db, p["player_id"], 6)
            if not found:
                return None
            return Fact(f"Viewed with {p['full_name']}", f"People who viewed {p['full_name']} also viewed " + ", ".join(f"{name(r['player_id'])} ({r['viewers']} of {r['audience']} users)" for r in found) + ".", note, f"player:{p['player_id']}", [r["player_id"] for r in found], plan=describe_plan(q, "Learned from shared visits"))
        seen = audience_service.player_audience(db, p["player_id"])
        place = f", number {seen['rank']} of {seen['players']} players" if seen["rank"] else ""
        return Fact(f"Audience of {p['full_name']}", f"{seen['viewers']} users viewed {p['full_name']}{place}.", note, f"player:{p['player_id']}", [p["player_id"]], plan=describe_plan(q, "Counted different users"))
    position = q.roles[0] if q.roles else None
    if has(r"trending", q.low):
        items, title = audience_service.trending(db, position, 8), "Trending players"
        lines = [f"{name(i['player_id'])} ({i['detail']})" for i in items]
    elif has(r"gems?|underrated|overlooked|radar", q.low):
        items, title = audience_service.hidden_gems(db, position, 8), "Good players few people look at"
        lines = [f"{name(i['player_id'])} ({i['detail'].lower()})" for i in items]
    else:
        days = 7 if has(r"this week|last week|past week|last 7 days", q.low) else 30 if has(r"this month|last month|last 30 days", q.low) else None
        items, title = audience_service.most_viewed(db, days, position, 8), "Most viewed players" + (f", last {days} days" if days else "")
        lines = [f"{name(i['player_id'])} ({i['viewers']} users)" for i in items]
    if not items:
        return Fact(title, "Nobody stands out at the moment.", note, plan=describe_plan(q, title))
    return Fact(title, f"{title}: {', '.join(lines)}.", note, "league", [i["player_id"] for i in items], table={"columns": ["#", "Player", "Users"], "rows": [[n, name(i["player_id"]), i["viewers"]] for n, i in enumerate(items, 1)]}, plan=describe_plan(q, title))


def _shared(db, q: Query) -> Fact | None:
    """Questions that read the same with and without a player's name."""
    low = q.low
    if has(AUDIENCE, low):
        if fact := audience(db, q):
            return fact
    if has(r"plays? like|similar|similarly|same style|play the same", low) and len(q.teams) == 1 and not q.players and has(r"teams?|plays?", low):
        if alike := team_style.similar_teams(db, q.teams[0]["nba_team_id"]):
            teams = data.team_list(db)
            t = q.teams[0]
            return Fact(f"Teams that play like the {t['full_name']}", f"The {teams.at[alike[0]['team_id'], 'full_name']} play most like the {t['full_name']} ({100 * alike[0]['similarity']:.0f}%{': ' + ', '.join(alike[0]['shared']) if alike[0]['shared'] else ''}). Next: " + ", ".join(f"{teams.at[a['team_id'], 'full_name']} {100 * a['similarity']:.0f}%" for a in alike[1:]) + ".", "Compared by pace, shot selection and how possessions are won, not by strength.", f"team:{t['nba_team_id']}", [], [a["team_id"] for a in alike], plan=describe_plan(q, "Nearest team styles"))
    if has(r"duos?|pair(?:s|ing|ings)?|two[- ]man|tandems?|chemistry|together|combinations?|shared minutes|on the court with|play(?:s|ed|ing)? with", low) and not tf.shot_words(q)[0]:
        if fact := tf.pair_answer(db, q):
            return fact
    if has(r"improv\w*|declin\w*|hott?est|coldest|rising|trending|better lately|slump\w*|heating up|cooling", low) and (not q.players or q.metrics):
        return form_change(db, q)
    return None


def _about_players(db, q: Query) -> Fact | None:
    low = q.low
    if has(AUDIENCE, low):
        return audience(db, q)
    if len(q.players) >= 5 and has(r"line[- ]?ups?|five|together|unit|do|fit|rate", low):
        return tf.lineup(db, q)
    if len(q.players) == 1 and has(r"teammates?|fits?|complement\w*|partners?|alongside|next to", low) and has(r"ideal|best|good|fits?|should|complement\w*|perfect|who", low) and not has(r"net rating|minutes|duo|pairing|played with", low):
        return tf.teammate_fit(db, q)
    if fact := _shared(db, q):
        return fact
    if len(q.players) == 2 and not q.opponents and has(r"guard(?:s|ed|ing)?\b|defend(?:s|ed|ing|er)?\b|match[- ]?ups?|stop(?:s|ped)?|against|head[- ]to[- ]head", low):
        return tf.duel(db, q)
    if tf.shot_words(q)[0] and not has(r"guarded|defended", low):
        return tf.shot_answer(db, q)
    if tf.quarter(q):
        return quarter_scoring(db, q)
    if has(r"records?|wins? and loss\w*|win[- ]loss", low) and not q.metrics:
        return player_record(db, q)
    if q.thresholds and has(r"games?|times|often|how many", low) and not has(r"averag\w*", low):
        return player_game_count(db, q)
    if has(SINGLE, low) and (q.metrics or has(r"best (?:game|performance|night)s?", low)):
        return player_single_game(db, q)
    if has(r"home (?:or|and|vs\.?|versus|than) (?:\w+ ){0,3}(?:away|road)|(?:away|road) (?:or|and|vs\.?|than) (?:\w+ ){0,3}home|wins (?:or|and|than) (?:\w+ )?losses|losses and wins", low):
        return player_split(db, q)
    if q.metrics and len(q.players) == 1 and has(r"rank\w*|what place|where (?:does|do|did|is)", low):
        return player_rank(db, q)
    if len(q.players) >= 2:
        return player_compare(db, q)
    if q.metrics:
        return player_value(db, q)
    return player_summary(db, q) if q.sliced and not has(r"similar|like|guard\w*|defend\w*|trouble|struggl\w*", low) else None


def _about_teams_and_groups(db, q: Query) -> Fact | None:
    low = q.low
    superlative = bool(has(SUPERLATIVE, low))
    team_words = bool(has(r"teams?|franchises?|clubs?|squads?", low))
    about_team = team_words or bool(q.teams)
    metrics = tf.team_metrics(q)
    other_metrics = [m for m in metrics if m.key not in ("wins", "losses")]

    if (q.teams or q.roster) and has(r"sign|trade for|target\w*|acquire|add|recruit|bring in|need\w*|missing|improve with|should .* get|reinforce\w*|help", low) and has(r"who|which|what|players?|guards?|forwards?|centers?|need\w*", low):
        return tf.targets(db, q)
    if fact := _shared(db, q):
        return fact
    if has(r"line[- ]?ups?|similar|teammates?", low):
        return None
    if has(r"streaks?|in a row|consecutive|straight (?:wins|losses)", low):
        return tf.streaks(db, q)
    if tf.shot_words(q)[0]:
        return tf.shot_answer(db, q)
    if tf.quarter(q):
        return tf.team_quarter(db, q) if about_team or not has(r"who|players?|scorers?", low) else quarter_scoring(db, q)
    if has(r"league[- ]?(?:average|wide)|average (?:nba )?(?:team|player)|(?:of|for|per) (?:a|an average|the average) (?:team|player)", low) or (has(r"average", low) and has(r"league|of (?:all )?(?:the )?players|of (?:all )?(?:the )?teams", low) and not superlative and not q.thresholds):
        return tf.league_average(db, q)
    if q.overtime and has(r"how many|games?|most|record", low):
        return tf.game_extremes(db, q)

    both = {t["nba_team_id"] for t in q.teams + q.opponents}
    if len(both) == 2 and has(r"won|win|beat\w*|score|results?|games?|played?|meet|met|happened|head[- ]to[- ]head|series|hosted|lose|lost|against|did", low) and not has(r"more (?:games|wins)|most|better", low) and not [m for m in other_metrics if m.key not in ("points", "opp_points")]:
        return tf.head_to_head(db, q)
    extreme = has(r"(?:biggest|largest|highest|closest|narrowest|lowest|most|fewest|worst|heaviest|tightest)(?:[- ]\w+){0,3} (?:games?|win|wins|victor\w*|loss|defeat|margin|blow ?outs?)|blow ?outs?|margin of victory|points in (?:a|one|any) game|in (?:a|one|any) (?:single )?game", low) and not has(r"per game|averag\w*|a game", re.sub(r"\bin a game\b", "", low))
    if extreme and not has(r"who |players?|games? (?:with|over)|won the most games|most games|most wins|fewest wins|close games", low) and (about_team or has(r"scoring game|highest[- ]scor\w+|biggest|largest|closest|margin|blow", low)):
        return tf.game_extremes(db, q)
    if q.day and has(r"who won|games?|results?|scores?|happened|played?", low) and not has(r"\bwho (?:scored|had)|most|points", low):
        return tf.day_games(db, q)
    if has(r"standings?|seed\w*|finish\w*|place|first in|last in|top of|bottom of|conference", low) and (q.teams or q.conference or has(r"standings?", low)) and not other_metrics and not has(r"players?|scorers?", low):
        return tf.standing_answer(db, q)

    if len(q.teams) == 1 and not other_metrics and not q.metrics and has(r"records?|win|wins|won|lose|loses|lost|losses|home|road|away|games|how did|how (?:good|well)", low) and not has(r"roster|players?", low):
        return tf.team_record(db, q)
    if len(q.teams) == 1 and [m for m in metrics if m.key == "close"]:
        return tf.team_record(db, q)
    if q.teams and not q.metrics and not q.thresholds and has(r"roster|who plays?|players|squad", low):
        return roster(db, q)
    if q.teams and metrics and not has(r"\bwho\b(?! won)|players?|leading scorers?|top scorers?", low):
        return tf.team_value(db, q, other_metrics or metrics)
    if q.teams:
        q = replace(q, roster=q.teams, teams=[])
    if team_words and (trait := next((m for m in q.metrics if m.key in ("height", "weight", "age", "experience")), None)):
        return tf.team_trait(db, q, trait)
    if team_words:
        return tf.team_top(db, q, (other_metrics or metrics)[0]) if metrics else None

    if q.roster and not q.metrics and not q.thresholds and has(r"roster|who plays?|players?|squad|how many", low):
        return roster(db, q)
    if q.thresholds and has(r"games?\b|times|nights", low) and not has(r"(?:a|per|each|every) game|averag\w*|games played", low):
        return player_game_count(db, q)
    if q.thresholds or q.percents:
        return player_list(db, q)
    if has(r"how many", low) and any(m.key in ("double_doubles", "triple_doubles") for m in q.metrics):
        return counted_total(db, q)
    if has(SINGLE, low) and (q.metrics or has(r"best (?:game|performance|night)s?|performances?|performer", low)):
        return player_single_game(db, q)
    if q.metrics and (superlative or q.roster or q.roles or q.max_age is not None or q.min_age is not None or q.sliced or has(r"who|which|players?|scorers?|shooters?|list|show|find", low)):
        return player_top(db, q, q.metrics[0])
    return None
