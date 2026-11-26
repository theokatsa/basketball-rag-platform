"""Calculations about teams, games, shots, pairs, matchups and lineups. See fact_engine.py."""

from __future__ import annotations

import re
from dataclasses import replace

import pandas as pd
from sqlalchemy import text

from app.services import league_data as data
from app.services.cache import rows
from app.services.insight_service import SKILLS, analyze_lineup, player_fit
from app.services.metrics import TEAM_METRICS, Metric, find_metrics
from app.services.query_planner import has
from app.services.recommend_service import team_targets
from app.services.question_reader import LEAST, TOP, WORST, Fact, Query, descending, describe_plan, eligible, group_words, ids_of, slice_games, sum_players, sum_teams, wants_total, where_words
from app.core.config import ACTIVE_SEASON_SQL

NEED_WORDS = {"tpa": "threes attempted", "fta": "free throws attempted", "fga": "shots", "defended_fga": "shots defended", "minutes": "minutes"}
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "last": 4, "final": 4}
TIES = "Ties are ordered by point difference, not the league's tiebreakers."

# words, column, value, name. One type and one area may be combined ("step-back threes").
SHOT_TYPES = [
    (r"alley[- ]?oops?", "action", "Alley Oop", "alley-oops"), (r"put ?backs?", "action", "Putback", "putbacks"), (r"tip[- ]?ins?", "action", "Tip", "tip-ins"),
    (r"dunk\w*|slams?", "action", "Dunk", "dunks"), (r"finger rolls?", "action", "Finger Roll", "finger rolls"), (r"lay[- ]?ups?", "action", "Layup", "layups"),
    (r"float(?:er|ers|ing shots?)", "action", "Floating", "floaters"), (r"step[- ]?backs?", "action", "Step Back", "step-back shots"), (r"hook(?: shot)?s?|hooks", "action", "Hook", "hook shots"),
    (r"pull[- ]?ups?", "action", "Pullup|Pull-Up", "pull-up shots"), (r"fade[- ]?aways?", "action", "Fadeaway", "fadeaways"), (r"turn[- ]?arounds?", "action", "Turnaround", "turnaround shots"),
    (r"bank shots?", "action", "Bank", "bank shots"),
]
_THREES = r"(?: (?:threes?|3s?|three[- ]?point(?:er)?s?))?"
SHOT_AREAS = [
    (rf"left corner{_THREES}", "zone", ["corner-L"], "left corner threes"), (rf"right corner{_THREES}", "zone", ["corner-R"], "right corner threes"), (rf"corners?{_THREES}", "zone", ["corner-L", "corner-R"], "corner threes"),
    (rf"above[- ]the[- ]break{_THREES}", "basic", ["Above the Break 3"], "above-the-break threes"), (r"(?:deep|long|logo) (?:threes?|3s?|three[- ]pointers?|range)", "zone", ["deep"], "deep threes"),
    (r"top of the (?:key|arc)", "zone", ["top"], "threes from the top"), (r"wing threes?|(?:from|on) the wings?", "zone", ["wing-L", "wing-R", "slot-L", "slot-R"], "wing threes"),
    (r"mid[- ]?range\w*|long twos?", "basic", ["Mid-Range"], "mid-range shots"), (r"baseline", "zone", ["base-L", "base-R"], "baseline twos"), (r"(?:near|around|from) the free[- ]throw line area|elbows?", "zone", ["ft"], "free-throw-line area shots"),
    (r"(?:at|near|around) the (?:rim|basket|hoop)|restricted area|point[- ]blank", "basic", ["Restricted Area"], "shots at the rim"), (r"(?:in|from|inside) the paint|paint (?:points|scoring|shots)|paint", "basic", ["Restricted Area", "In The Paint (Non-RA)"], "shots in the paint"),
]


def record(games) -> str:
    wins = int(games.won.sum())
    return f"{wins}-{len(games) - wins}"


def day_of(d) -> str:
    return f"{d.day} {d:%B %Y}"


def team_metrics(q: Query) -> list[Metric]:
    return find_metrics(q.low, TEAM_METRICS)


def _frame(db, q: Query) -> pd.DataFrame:
    frame = slice_games(data.team_games(db), q, "team")
    return frame[frame.overtime] if q.overtime else frame


def _team_fact(title, answer, detail, team_ids, plan, table=None, entity=None) -> Fact:
    return Fact(title, answer, detail, entity or (f"team:{team_ids[0]}" if len(team_ids) == 1 else "league"), [], [int(i) for i in team_ids], table, plan)


def standings(db) -> pd.DataFrame:
    return sum_teams(db, Query("")).sort_values(["won", "margin"], ascending=False)


def team_record(db, q: Query) -> Fact | None:
    team = q.teams[0]
    tid, name = team["nba_team_id"], team["full_name"]
    full = data.team_games(db)
    full = full[full.team == tid]
    own = _frame(db, q)
    own = own[own.team == tid]
    where = where_words(q) + (" in overtime games" if q.overtime else "")
    if has(r"close games?|clutch|tight games?", q.low):
        own = own[own.margin.abs() <= 5]
        where += " in games decided by 5 points or fewer"
    if not len(own):
        return _team_fact(f"{name} record", f"The {name} played no games{where}.", "", [tid], describe_plan(q, "Record"))
    wins = int(own.won.sum())
    answer = f"The {name} were {record(own)}{where}: {wins} wins and {len(own) - wins} losses in {len(own)} games, {own.points.mean():.1f} points scored and {own.a_points.mean():.1f} allowed per game."
    if len(own) == len(full):
        seats = standings(db)
        conference = seats.loc[tid, "conference"]
        detail = f"Place in the {conference}: {seats[seats.conference == conference].index.get_loc(tid) + 1}. Home {record(full[full.home])}, road {record(full[~full.home])}."
    else:
        detail = f"Whole season: {record(full)}."
    if len(own) <= 6:
        teams = data.team_list(db)
        detail += " Games: " + "; ".join(f"{day_of(r.game_date)}: {'won' if r.won else 'lost'} {r.points:.0f}-{r.a_points:.0f} {'vs' if r.home else 'at'} {teams.loc[r.opp, 'nickname']}" for r in own.itertuples()) + "."
    return _team_fact(f"{name} record{where}", answer, detail, [tid], describe_plan(q, "Record"), {"columns": ["Games", "Wins", "Losses", "Scored", "Allowed"], "rows": [[len(own), wins, len(own) - wins, f"{own.points.mean():.1f}", f"{own.a_points.mean():.1f}"]]})


def standing_answer(db, q: Query) -> Fact | None:
    seats = standings(db)
    if q.teams:
        tid, name = q.teams[0]["nba_team_id"], q.teams[0]["full_name"]
        conference = seats.loc[tid, "conference"]
        own = seats[seats.conference == conference]
        r = seats.loc[tid]
        return _team_fact(f"{name} standing", f"The {name} finished number {own.index.get_loc(tid) + 1} in the {conference} with {r.won:.0f} wins and {r.gp - r.won:.0f} losses (number {seats.index.get_loc(tid) + 1} overall).", TIES, [tid], describe_plan(q, "Standings"))
    own = seats[seats.conference == q.conference] if q.conference else seats
    if has(r"last|worst|bottom", q.low):
        own = own[::-1]
    lines = [f"{r.full_name} {r.won:.0f}-{r.gp - r.won:.0f}" for _, r in own.iterrows()]
    table = {"columns": ["#", "Team", "W", "L"], "rows": [[k, r.full_name, int(r.won), int(r.gp - r.won)] for k, (_, r) in enumerate(own.iterrows(), 1)]}
    return _team_fact(f"{q.conference + 'ern Conference' if q.conference else 'League'} standings", f"{lines[0]}. Then: {', '.join(lines[1:10])}.", TIES, list(own.index[:10]), describe_plan(q, "Standings"), table)


def quarter(q: Query) -> tuple[list[str], str] | None:
    if m := re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|last|final)[- ](?:quarter|period)s?\b", q.low, re.I):
        n = ORDINALS[m[1].lower()]
        return [f"q{n}"], f"{['first', 'second', 'third', 'fourth'][n - 1]} quarter"
    if m := re.search(r"\b(first|second)[- ]half\b(?! of the (?:season|year))", q.low, re.I):
        return (["q1", "q2"], "first half") if m[1].lower() == "first" else (["q3", "q4"], "second half")
    return None


def team_quarter(db, q: Query) -> Fact | None:
    columns, name = quarter(q)
    frame = _frame(db, q)
    frame = frame.assign(own=frame[columns].sum(axis=1), other=frame[[f"a_{c}" for c in columns]].sum(axis=1))
    frame["diff"] = frame.own - frame.other
    means = frame.groupby("team")[["own", "other", "diff"]].mean()
    teams = data.team_list(db)
    plan = describe_plan(q, f"Points in the {name}")
    if q.teams:
        tid = q.teams[0]["nba_team_id"]
        r = means.loc[tid]
        return _team_fact(
            f"{q.teams[0]['full_name']} in the {name}", f"The {q.teams[0]['full_name']} scored {r.own:.1f} and allowed {r.other:.1f} points in the {name}{where_words(q)} ({r['diff']:+.1f}),"
            f" number {int((means.own > r.own).sum()) + 1} in scoring and {int((means['diff'] > r['diff']).sum()) + 1} in point difference.", "", [tid], plan,
        )
    stat = "other" if has(r"allow\w*|defen\w*|conced\w*|give up", q.low) else "diff" if has(r"outscor\w*|margin|difference", q.low) else "own"
    label = {"own": "points scored", "other": "points allowed", "diff": "point difference"}[stat]
    down = stat != "other"
    if has(LEAST, q.low) or has(WORST, q.low):
        down = not down if has(WORST, q.low) else False
    elif has(r"most|highest", q.low):
        down = True
    ordered = means.sort_values(stat, ascending=not down)
    lines = [f"{teams.loc[i, 'full_name']} {r[stat]:.1f}" for i, r in ordered.head(6).iterrows()]
    table = {"columns": ["Team", label.capitalize()], "rows": [[teams.loc[i, "full_name"], f"{r[stat]:.1f}"] for i, r in ordered.head(10).iterrows()]}
    return _team_fact(f"Teams in the {name}", f"{lines[0]} {label} per game in the {name}{where_words(q)}, the {'highest' if down else 'lowest'}. Next: {', '.join(lines[1:])}.", "", list(ordered.index[:6]), plan, table)


def team_value(db, q: Query, metrics: list[Metric]) -> Fact | None:
    sums = sum_teams(db, q)
    chosen = [t for t in q.teams if t["nba_team_id"] in sums.index]
    lines, table = [], []
    for t in chosen:
        row = sums.loc[t["nba_team_id"]]
        for m in metrics[:3]:
            values = m.value(sums).astype(float)
            value = values[t["nba_team_id"]]
            place = int(((values < value) if m.lower else (values > value)).sum()) + 1
            shown = f"{m.total(row):.0f} in total ({m.show(value)} per game)" if wants_total(q, m) and m.key != "wins" else m.show(value)
            lines.append(f"The {t['full_name']}: {m.label.lower()}{where_words(q)} {shown}, number {place} of {len(values)}{' (lowest first)' if m.lower else ''}.")
            table.append([t["full_name"], m.label, m.show(value), place])
    if not lines:
        return None
    if len(chosen) > 1:
        m = metrics[0]
        values = m.value(sums).astype(float).loc[ids_of(chosen)].sort_values(ascending=not descending(q, m))
        lines.insert(0, f"{sums.loc[values.index[0], 'full_name']}: {m.show(values.iloc[0])} {m.label.lower()}, against " + ", ".join(f"{sums.loc[i, 'full_name']} {m.show(v)}" for i, v in values.iloc[1:].items()) + ".")
        if values.iloc[0] == values.iloc[1]:
            lines[0] = f"{' and '.join(sums.loc[values.index, 'full_name'])} are level: {m.show(values.iloc[0])} {m.label.lower()}."
    labels = ", ".join(m.label.lower() for m in metrics[:3])
    return _team_fact(f"{', '.join(t['full_name'] for t in chosen)}: {labels}", " ".join(lines), "", ids_of(chosen), describe_plan(q, f"Calculated: {labels}"), {"columns": ["Team", "Statistic", "Value", "Rank"], "rows": table})


def team_top(db, q: Query, metric: Metric) -> Fact | None:
    sums = sum_teams(db, q)
    if q.conference:
        sums = sums[sums.conference == q.conference]
    values = metric.value(sums).astype(float).dropna()
    down = descending(q, metric)
    as_total = metric.total is not None and metric.key != "wins" and wants_total(q, metric)
    if as_total:
        values = metric.total(sums).astype(float)
    order = pd.DataFrame({"v": values, "m": sums.margin.reindex(values.index)}).sort_values(["v", "m"], ascending=[not down, not down])
    lines = [(sums.loc[i, "full_name"], f"{r.v:.0f}" if as_total else metric.show(r.v), int(i)) for i, r in order.head(TOP).iterrows()]
    best = sums.loc[lines[0][2]]
    extra = f" ({best.won:.0f}-{best.gp - best.won:.0f})" if metric.key in ("wins", "losses") else f" ({best.close_wins:.0f} wins in {best.close_games:.0f})" if metric.key == "close" else ""
    group = f" in the {q.conference}" if q.conference else ""
    label = ("total " if as_total else "") + metric.label.lower()
    return _team_fact(
        f"Teams by {label}{where_words(q)}{group}", f"{lines[0][0]}: {lines[0][1]} {label}{where_words(q)}{extra}, the {'highest' if down else 'lowest'}{group}. Next: {', '.join(f'{n} {v}' for n, v, _ in lines[1:])}.", "",
        [i for *_, i in lines], describe_plan(q, f"Teams ranked by {label}, {'highest' if down else 'lowest'} first"), {"columns": ["#", "Team", metric.label], "rows": [[k, n, v] for k, (n, v, _) in enumerate(lines, 1)]},
    )


def team_trait(db, q: Query, metric: Metric) -> Fact | None:
    """Average height, weight, age or experience of a team, weighted by minutes played."""
    folk = sum_players(db, Query(""))
    values = metric.value(folk).astype(float)
    known = values.notna() & folk.team.notna()
    weight = folk.minutes[known]
    means = (values[known] * weight).groupby(folk.team[known]).sum() / weight.groupby(folk.team[known]).sum()
    teams = data.team_list(db)

    def show(v):
        return f"{int(v // 12)}'{v % 12:.1f}\"" if metric.key == "height" else f"{v:.1f}{metric.suffix}"

    down = descending(q, metric)
    order = means.sort_values(ascending=not down)
    lines = [f"{teams.loc[int(i), 'full_name']} {show(v)}" for i, v in order.head(8).items()]
    label = {"age": "average age", "height": "average height", "weight": "average weight", "experience": "average seasons in the league"}[metric.key]
    return _team_fact(f"Teams by {label}", f"{lines[0]}: the {'highest' if down else 'lowest'} {label}, weighted by minutes. Next: {', '.join(lines[1:])}.", "", [int(i) for i in order.index[:8]], describe_plan(q, f"Teams ranked by {label}"))


def streaks(db, q: Query) -> Fact | None:
    losing = bool(has(r"los\w+ streaks?|lost (?:the )?most in a row|straight loss\w*|consecutive loss\w*|losses in a row", q.low))
    teams = data.team_list(db)
    best = []
    for team, games in data.team_games(db).groupby("team"):
        run, start, top = 0, None, (0, None, None)
        for r in games.itertuples():
            if r.won == losing:
                run = 0
                continue
            run, start = run + 1, start if run else r.game_date
            if run > top[0]:
                top = (run, start, r.game_date)
        last = games.won.iloc[-1]
        current = int((games.won[::-1] == last).cumprod().sum())
        best.append((*top, int(team), current if last else -current))
    if q.teams:
        best = [b for b in best if b[3] in ids_of(q.teams)]
    best.sort(key=lambda b: -b[0])
    n, a, b, team, current = best[0]
    kind = "losing" if losing else "winning"
    name = teams.loc[team, "full_name"]
    if q.teams:
        end = f" They ended the season on {abs(current)} straight {'wins' if current > 0 else 'losses'}." if abs(current) > 1 else ""
        answer = f"The longest {kind} streak of the {name} was {n} game{'' if n == 1 else 's'}, from {day_of(a)} to {day_of(b)}.{end}"
    else:
        answer = f"{name} had the longest {kind} streak: {n} games, from {day_of(a)} to {day_of(b)}. Next: " + ", ".join(f"{teams.loc[x[3], 'full_name']} {x[0]}" for x in best[1:6]) + "."
    return _team_fact(f"Longest {kind} streak", answer, "", [team], describe_plan(q, f"Longest {kind} streak"))


def game_extremes(db, q: Query) -> Fact | None:
    """Highest score, biggest win, closest game, overtime counts."""
    frame = _frame(db, q)
    teams = data.team_list(db)
    own = frame[frame.team.isin(ids_of(q.teams))] if q.teams else frame
    if not len(own):
        return None
    if q.overtime:
        longest = own.sort_values("minutes", ascending=False).iloc[0]
        detail = f"The longest: {teams.loc[longest.team, 'full_name']} {longest.points:.0f}-{longest.a_points:.0f} {teams.loc[longest.opp, 'full_name']} on {day_of(longest.game_date)}."
        if q.teams:
            answer = f"The {q.teams[0]['full_name']} played {len(own)} overtime games{where_words(q)} ({record(own)})."
        else:
            by_team = own.groupby("team").size().sort_values(ascending=False)
            count = f"{own.game_id.nunique()} games went to overtime{where_words(q)}."
            most = f"The {teams.loc[by_team.index[0], 'full_name']} played the most overtime games: {by_team.iloc[0]}."
            answer = f"{most} {count}" if has(r"which|most|who", q.low) and not has(r"how many", q.low) else f"{count} {most}"
        return _team_fact("Overtime games", answer, detail, ids_of(q.teams), describe_plan(q, "Counted overtime games"), entity=None if q.teams else "league")
    if has(r"closest|narrowest|tightest", q.low):
        pick, label = own[own.won].sort_values(["margin", "game_date"]), "closest game"
    elif has(r"(?:biggest|worst|heaviest|largest) (?:\w+ )?(?:loss|defeat)", q.low):
        pick, label = own.sort_values("margin"), "biggest loss"
    elif has(r"combined|total points|by both teams", q.low):
        pick, label = own[own.won].assign(both=own.points + own.a_points).sort_values("both", ascending=bool(has(LEAST, q.low))), "combined score"
    elif has(r"blow ?outs?|margin|one[- ]sided", q.low) or (has(r"biggest|largest", q.low) and has(r"wins?|won|victor\w*", q.low)):
        pick, label = own.sort_values("margin", ascending=False), "biggest win"
    elif has(LEAST, q.low):
        pick, label = own.sort_values("points"), "fewest points"
    else:
        pick, label = own.sort_values("points", ascending=False), "most points"

    def line(r):
        return f"{teams.loc[r.team, 'full_name']} {r.points:.0f}-{r.a_points:.0f} {'vs' if r.home else 'at'} the {teams.loc[r.opp, 'full_name']} on {day_of(r.game_date)} (margin {abs(r.margin):.0f}{', overtime' if r.overtime else ''})"

    top = list(pick.head(5).itertuples())
    table = {"columns": ["Team", "Score", "Opponent", "Date", "Margin"], "rows": [[teams.loc[r.team, "full_name"], f"{r.points:.0f}-{r.a_points:.0f}", teams.loc[r.opp, "full_name"], f"{r.game_date:%Y-%m-%d}", int(r.margin)] for r in top]}
    return _team_fact(f"Games: {label}{where_words(q)}", line(top[0]) + ".", "Next: " + "; ".join(map(line, top[1:])) + "." if top[1:] else "", [top[0].team, top[0].opp], describe_plan(q, f"Games by {label}"), table, f"game:{top[0].game_id}")


def head_to_head(db, q: Query) -> Fact | None:
    """Games between two teams."""
    a, b = list({t["nba_team_id"]: t for t in q.teams + q.opponents}.values())
    frame = _frame(db, replace(q, opponents=[], home=None))
    games = frame[(frame.team == a["nba_team_id"]) & (frame.opp == b["nba_team_id"])]
    if q.home is not None:
        games = games[games.home == q.home]
    plan, title = describe_plan(q, "Head to head"), f"{a['full_name']} against {b['full_name']}"
    ids = [a["nba_team_id"], b["nba_team_id"]]
    if not len(games):
        return _team_fact(title, f"The {a['full_name']} and the {b['full_name']} played no such game.", "", ids, plan)

    def line(r):
        winner, loser = (a, b) if r.won else (b, a)
        return f"the {winner['full_name']} beat the {loser['full_name']} {max(r.points, r.a_points):.0f}-{min(r.points, r.a_points):.0f}{' after overtime' if r.overtime else ''} on {day_of(r.game_date)}, hosted by the {(a if r.home else b)['full_name']}"

    lines = [line(r) for r in games.itertuples()]
    table = {"columns": ["Date", a["full_name"], b["full_name"], "Winner"], "rows": [[f"{r.game_date:%Y-%m-%d}", int(r.points), int(r.a_points), a["full_name"] if r.won else b["full_name"]] for r in games.itertuples()]}
    if len(games) == 1:
        answer, detail = lines[0][0].upper() + lines[0][1:] + ".", ""
    else:
        answer, detail = f"The {a['full_name']} won {int(games.won.sum())} of {len(games)} games against the {b['full_name']}: " + "; ".join(lines) + ".", ""
    return _team_fact(title, answer, detail, ids, plan, table, f"game:{games.iloc[0].game_id}")


def day_games(db, q: Query) -> Fact | None:
    won = _frame(db, q)
    won = won[won.won]
    if q.teams:
        won = won[won.team.isin(ids_of(q.teams)) | won.opp.isin(ids_of(q.teams))]
    teams, plan = data.team_list(db), describe_plan(q, "Games on a date")
    if not len(won):
        return _team_fact("Games", f"There were no such games{where_words(q)}.", "", ids_of(q.teams), plan)
    return _team_fact(f"Games{where_words(q)}", "; ".join(f"The {teams.loc[r.team, 'full_name']} beat the {teams.loc[r.opp, 'full_name']} {r.points:.0f}-{r.a_points:.0f}" for r in won.itertuples()) + ".", "", list(won.team), plan)


def league_average(db, q: Query) -> Fact | None:
    sums = sum_teams(db, q).select_dtypes("number").sum()
    lines = []
    if not has(r"players?", q.low):
        lines = [f"The league average {m.label.lower()}{where_words(q)} was {m.show(m.value(sums))}{' per team and game' if m.total is not None else ''}." for m in team_metrics(q)[:3] if m.key not in ("wins", "losses", "close")]
    if not lines:
        people = sum_players(db, q).select_dtypes("number")
        for m in q.metrics[:2]:
            if m.season_only:
                lines.append(f"The average {m.label.lower()} of a player was {m.show(m.value(people).mean())}.")
            else:
                lines.append(f"The average {m.label.lower()} was {m.show(m.value(people.sum()))} per player and game.")
    return Fact("League averages", " ".join(lines), "Calculated from all games.", plan=describe_plan(q, "League average")) if lines else None


# ------------------------------------------------------------------ shots

def shot_words(q: Query) -> tuple[list, list[str]]:
    tests, names, left = [], [], q.low
    for table in (SHOT_TYPES, SHOT_AREAS):
        for words, column, value, name in table:
            if m := re.search(rf"\b(?:{words})\b", left, re.I):
                tests.append((column, value))
                names.append(name)
                left = left[: m.start()] + " " * (m.end() - m.start()) + left[m.end() :]
                break
    if tests and tests[0][0] == "action" and len(tests) == 1 and re.search(r"\b(?:threes?|3s|three[- ]pointers?)\b", left, re.I):
        tests.append(("three", [True]))
        names.append("(threes)")
    return tests, names


def shot_answer(db, q: Query) -> Fact | None:
    tests, names = shot_words(q)
    teams, folk = data.team_list(db), data.people(db)
    by_team = not q.players and (bool(q.teams) or bool(has(r"teams?", q.low)))
    defense = by_team and has(r"allow\w*|defen\w*|conced\w*|give up|opponents?", q.low)
    where = ""
    if q.opponents:
        frame = data.shots(db, teams.loc[q.opponents[0]["nba_team_id"], "abbreviation"])
        where = f" against the {q.opponents[0]['full_name']}"
    else:
        frame = data.shots(db)
    if part := quarter(q):
        frame = frame[frame.period.isin([int(c[1:]) for c in part[0]])]
        where += f" in the {part[1]}"
    for column, value in tests:
        frame = frame[frame[column].str.contains(value, regex=True)] if column == "action" else frame[frame[column].isin(value)]
    name = " ".join(names)
    plan_name = f"Shots: {name}{where}"
    if defense:
        return _team_shots_allowed(db, q, tests, name)
    key = "team" if by_team else "player_id"
    sums = frame.groupby(key)[["tries", "made"]].sum()
    if not len(sums):
        return None
    tries, made = int(frame.tries.sum()), int(frame.made.sum())
    average = made / max(tries, 1)

    def title(i):
        return teams.loc[i, "full_name"] if by_team else folk.loc[i, "full_name"]

    chosen = ids_of(q.teams) if by_team else ids_of(q.players)
    ids = {"team_ids" if by_team else "player_ids": chosen}
    if chosen:
        table = [[title(i), int(sums.loc[i, "made"]), int(sums.loc[i, "tries"]), f"{100 * sums.loc[i, 'made'] / sums.loc[i, 'tries']:.1f}%"] for i in chosen if i in sums.index]
        if len(table) > 1:
            table.sort(key=lambda r: -r[1] if has(r"more|most|made", q.low) else -float(r[3][:-1]))
        lines = [f"{n} made {m} of {t} {name}{where} ({p}, league {100 * average:.1f}%)." for n, m, t, p in table] + [f"{title(i)} took no {name}{where}." for i in chosen if i not in sums.index]
        return Fact(f"{', '.join(title(i) for i in chosen)}: {name}", " ".join(lines), "", f"{'team' if by_team else 'player'}:{chosen[0]}", **ids, table={"columns": ["Name", "Made", "Attempted", "%"], "rows": table}, plan=describe_plan(q, plan_name))
    if not by_team:
        sums = sums[sums.index.isin(eligible(folk, None, q, strict=False).index)]
    attempts = bool(has(r"take|takes|took|attempt\w*|shoot the most|rel\w+ on|shots taken", q.low))
    accuracy = bool(has(r"percent\w*|accura\w*|best|efficient|better|well|worst|shooters?", q.low)) and not attempts and not has(r"most|made|makes|fewest", q.low)
    note = f"League: {made} of {tries} ({100 * average:.1f}%)."
    if accuracy:
        least = 1 if by_team else max(20, int(0.12 * sums.tries.nlargest(30).mean()))
        prior = 0 if by_team else 40
        pool = sums[sums.tries >= least]
        order = ((pool.made + prior * average) / (pool.tries + prior)).sort_values(ascending=bool(has(WORST, q.low)))
        label, verb = "percentage", "was the worst shooter on" if has(WORST, q.low) else "was the best shooter on"
        if not by_team:
            note = f"At least {least} attempts; small samples are pulled toward the league average of {100 * average:.1f}%."
    else:
        order = sums["tries" if attempts else "made"].sort_values(ascending=bool(has(LEAST, q.low)))
        label, verb = ("attempts", "took the most") if attempts else ("makes", "made the most")
        if has(LEAST, q.low):
            verb = verb.replace("most", "fewest")
    if not len(order):
        return None
    best = list(order.index[:TOP])
    stats = {i: f"{sums.loc[i, 'made']:.0f} of {sums.loc[i, 'tries']:.0f} ({100 * sums.loc[i, 'made'] / sums.loc[i, 'tries']:.1f}%)" for i in best}
    group = f" among {group_words(q)}" if group_words(q) and not by_team else ""
    return Fact(
        f"{name.capitalize()} by {label}{where}", f"{title(best[0])} {verb} {name}{where}{group}: {stats[best[0]]}. Next: {'; '.join(f'{title(i)} {stats[i]}' for i in best[1:])}.", note, "league", **{"team_ids" if by_team else "player_ids": [int(i) for i in best]},
        table={"columns": ["#", "Name", "Made", "Attempted", "%"], "rows": [[k, title(i), int(sums.loc[i, "made"]), int(sums.loc[i, "tries"]), f"{100 * sums.loc[i, 'made'] / sums.loc[i, 'tries']:.1f}%"] for k, i in enumerate(best, 1)]}, plan=describe_plan(q, f"{plan_name}, ranked by {label}"),
    )


def _team_shots_allowed(db, q: Query, tests, name) -> Fact | None:
    """Shots given up by each team's defense, from this kind of shot."""
    teams = data.team_list(db)
    out = {}
    for tid, t in teams.iterrows() if not q.teams else [(i, teams.loc[i]) for i in ids_of(q.teams)]:
        frame = data.shots(db, t.abbreviation)
        for column, value in tests:
            frame = frame[frame[column].str.contains(value, regex=True)] if column == "action" else frame[frame[column].isin(value)]
        out[tid] = (int(frame.made.sum()), int(frame.tries.sum()))
    if q.teams:
        tid = q.teams[0]["nba_team_id"]
        made, tries = out[tid]
        return _team_fact(f"{name} allowed", f"The {teams.loc[tid, 'full_name']} allowed {made} of {tries} {name} ({100 * made / max(tries, 1):.1f}%).", "", [tid], describe_plan(q, f"Shots allowed: {name}"))
    volume = bool(has(r"most|fewest|attempts|made", q.low))
    order = sorted(out, key=lambda i: out[i][0] if volume else out[i][0] / max(out[i][1], 1), reverse=bool(has(r"most|worst|highest", q.low)))
    lines = [f"{teams.loc[i, 'full_name']} {out[i][0]} of {out[i][1]} ({100 * out[i][0] / max(out[i][1], 1):.1f}%)" for i in order[:6]]
    return _team_fact(f"{name} allowed", f"{lines[0]} {name} allowed. Next: {'; '.join(lines[1:])}.", "", order[:6], describe_plan(q, f"Shots allowed: {name}"))


# ------------------------------------------------------------------ pairs, matchups, lineups

PAIRS = f"select * from player_pairs where season = {ACTIVE_SEASON_SQL}"


def pair_answer(db, q: Query) -> Fact | None:
    folk, teams = data.people(db), data.team_list(db)

    def name(i):
        return folk.loc[i, "full_name"] if i in folk.index else "Unknown player"

    worst = bool(has(r"worst|weakest|lowest", q.low))
    if len(q.players) == 2:
        a, b = q.players
        found = rows(db, text(f"{PAIRS} and player_a = any(:ids) and player_b = any(:ids) order by minutes desc"), {"ids": ids_of(q.players)})
        plan = describe_plan(q, "Shared minutes")
        if not found:
            return Fact("Pair", f"{a['full_name']} and {b['full_name']} did not share the court for the same team.", "", plan=plan)
        r = found[0]
        return Fact(
            f"{a['full_name']} and {b['full_name']} together", f"{a['full_name']} and {b['full_name']} had a net rating of {r['net_rating']:+.1f} together: {r['off_rating']:.1f} points scored and {r['def_rating']:.1f} allowed per 100 possessions, in {r['minutes']:.0f} minutes over {r['games']} games.",
            "", f"player:{a['player_id']}", ids_of(q.players), [r["nba_team_id"]], plan=plan,
        )
    if len(q.players) > 2:
        return None
    if q.players:
        me = q.players[0]
        found = rows(db, text(f"{PAIRS} and :p in (player_a, player_b) and minutes >= 200 and net_rating is not null order by net_rating {'asc' if worst else 'desc'} limit 5"), {"p": me["player_id"]})
        if not found:
            return None
        others = [r["player_b"] if r["player_a"] == me["player_id"] else r["player_a"] for r in found]
        lines = [f"{name(i)} {r['net_rating']:+.1f} in {r['minutes']:.0f} minutes" for i, r in zip(others, found)]
        return Fact(f"{me['full_name']}: teammates by net rating", f"{me['full_name']}'s {'worst' if worst else 'best'} pairing was with {lines[0]}. Next: {'; '.join(lines[1:])}.", "At least 200 shared minutes.", f"player:{me['player_id']}", [me["player_id"], *others], plan=describe_plan(q, "Pairs by net rating"))
    chosen = q.teams or q.roster
    by_minutes = bool(has(r"most minutes|most (?:time|often)|played (?:the )?most", q.low))
    found = rows(
        db, text(f"{PAIRS} and minutes >= 200 and net_rating is not null {'and nba_team_id = any(:t)' if chosen else ''} order by {'minutes' if by_minutes else 'net_rating'} {'asc' if worst else 'desc'} limit 6"),
        {"t": ids_of(chosen)} if chosen else {},
    )
    if not found:
        return None
    lines = [f"{name(r['player_a'])} and {name(r['player_b'])} ({teams.loc[r['nba_team_id'], 'abbreviation']}) {r['net_rating']:+.1f} in {r['minutes']:.0f} minutes" for r in found]
    who = f" of the {chosen[0]['full_name']}" if chosen else " in the league"
    kind = "most used duo" if by_minutes else "worst duo by net rating" if worst else "best duo by net rating"
    return Fact(
        f"Duos{who}", f"The {kind}{who}: {lines[0]}. Next: {'; '.join(lines[1:])}.", "At least 200 shared minutes.", f"team:{chosen[0]['nba_team_id']}" if chosen else "league", [i for r in found for i in (r["player_a"], r["player_b"])], ids_of(chosen),
        {"columns": ["Duo", "Net rating", "Minutes"], "rows": [[f"{name(r['player_a'])} and {name(r['player_b'])}", f"{r['net_rating']:+.1f}", f"{r['minutes']:.0f}"] for r in found]}, describe_plan(q, "Pairs by net rating"),
    )


def duel(db, q: Query) -> Fact | None:
    """One player scoring against another as the defender."""
    a, b = q.players
    # "How did A do against B", "A guarded by B": A scores. "How did A guard B": B scores.
    passive = re.search(r"guarded by|defended by|against|as (?:his|the|a) defender|when .*(?:guards?|defends?)", q.low, re.I)
    off, guard = (b, a) if not passive and has(r"guard(?:s|ed|ing)?|defend(?:s|ed|ing)?|stop\w*|hold|held", q.low) else (a, b)
    found = rows(db, text(
        f"select * from player_matchups where season = {ACTIVE_SEASON_SQL} and ((off_player_id = :a and def_player_id = :b) or (off_player_id = :b and def_player_id = :a))"
    ), {"a": off["player_id"], "b": guard["player_id"]})
    plan = describe_plan(q, "Defensive matchups")
    if not found:
        return Fact("Matchup", f"There is no tracked matchup of at least 5 possessions between {a['full_name']} and {b['full_name']}.", "", plan=plan)
    lines = []
    for r in sorted(found, key=lambda r: r["off_player_id"] != off["player_id"]):
        scorer, stopper = (off, guard) if r["off_player_id"] == off["player_id"] else (guard, off)
        lines.append(
            f"{scorer['full_name']} scored {r['points']:.0f} points on {r['fgm']:.0f} of {r['fga']:.0f} shots ({r['tpm']:.0f} of {r['tpa']:.0f} threes) with {r['ast']:.0f} assists and {r['tov']:.0f} turnovers"
            f" when guarded by {stopper['full_name']}, over {r['possessions']:.0f} possessions in {r['games']} games ({100 * r['points'] / r['possessions']:.1f} points per 100)."
        )
    return Fact(f"{off['full_name']} against {guard['full_name']}", " ".join(lines), "", f"player:{off['player_id']}", ids_of(q.players), plan=plan)


def lineup(db, q: Query) -> Fact | None:
    five = q.players[:5]
    result = analyze_lineup(db, ids_of(five))
    if not result:
        return None
    names = ", ".join(p["full_name"] for p in five)
    good = sorted((s for s in result["stats"] if s["z"] > 0.7), key=lambda s: -s["z"])[:3]
    bad = sorted((s for s in result["stats"] if s["z"] < -0.7), key=lambda s: s["z"])[:3]
    detail = "".join(f"{word}: {', '.join(s['label'].lower() for s in group)}. " for word, group in (("Strengths", good), ("Weaknesses", bad)) if group)
    checks = "; ".join(f"{c['label'].lower()} {len(c['players'])} of {c['target']} wanted" for c in result["checks"])
    return Fact(
        f"Lineup estimate: {names}", f"The estimated net rating of {names} is {result['net']:+.1f} points per 100 possessions: offense {result['offense']:.1f}, defense {result['defense']:.1f}, with a league average of {result['league']:.1f}.",
        f"{detail}Balance: {checks}. This is a statistical estimate, not a simulation.", "league", ids_of(five), table={"columns": ["Statistic", "Lineup", "Average"], "rows": [[s["label"], f"{s['own']:.1f}", f"{s['base']:.1f}"] for s in result["stats"]]}, plan=describe_plan(q, "Lineup model"),
    )


def targets(db, q: Query) -> Fact | None:
    """Players a team should look at: "Who should the Lakers sign?"."""
    team = (q.teams or q.roster)[0]
    result = team_targets(db, team["nba_team_id"], 6, q.max_age, q.roles[0] if q.roles else None)
    if not result or not result["targets"]:
        return None
    folk = data.people(db)
    weak = [n["label"] for n in result["needs"] if n["z"] < -0.3][:3]
    lines = [f"{folk.at[t['player_id'], 'full_name']} ({', '.join(t['reasons'])})" for t in result["targets"]]
    return Fact(
        f"Targets for the {team['full_name']}", f"Statistically, {lines[0]} would help the {team['full_name']} most. Next: {'; '.join(lines[1:])}.",
        (f"Weakest skills of the squad: {', '.join(weak)}. " if weak else "") + "Contracts and availability are not in the database.", f"team:{team['nba_team_id']}", [t["player_id"] for t in result["targets"]], [team["nba_team_id"]], plan=describe_plan(q, "Team needs against players elsewhere"),
    )


def teammate_fit(db, q: Query) -> Fact | None:
    p = q.players[0]
    result = player_fit(db, p["player_id"])
    folk = data.people(db)
    ideal = [x for x in (result or {}).get("ideal_teammates", []) if x["player_id"] in folk.index]
    if not ideal:
        return None
    lines = [f"{folk.loc[x['player_id'], 'full_name']} ({', '.join(x['reasons']) or 'strong all-round'})" for x in ideal]
    weak = [SKILLS[s["key"]] for s in sorted(result["skills"], key=lambda s: s["z"]) if s["z"] < -0.25][:3]
    return Fact(
        f"Ideal teammates for {p['full_name']}", f"An ideal teammate for {p['full_name']} would be {lines[0]}. Next: {'; '.join(lines[1:])}.", (f"Skills to cover: {', '.join(weak)}. " if weak else "") + "A statistical fit: it covers weaker skills without needing the same ball.",
        f"player:{p['player_id']}", [x["player_id"] for x in ideal], plan=describe_plan(q, "Teammate fit"),
    )
