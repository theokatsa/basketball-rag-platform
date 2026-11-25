"""Reads a question into a Query: who it is about, which statistic, and which games."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from app.services import league_data as data
from app.services.metrics import PLAYER_METRICS, Metric, find_metrics
from app.services.query_planner import BIG_MEN, ROLES, find_ages, find_players, find_teams, find_thresholds, has
from app.services.text_utils import normalize_name

MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "october": 10, "november": 11, "december": 12}
SEASON_MONTHS = [10, 11, 12, 1, 2, 3, 4]
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20}
COUNTS = {
    "points": "points", "point": "points", "rebounds": "reb", "rebound": "reb", "boards": "reb", "assists": "ast", "assist": "ast", "steals": "stl", "steal": "stl",
    "blocks": "blk", "block": "blk", "threes": "tpm", "three": "tpm", "turnovers": "tov", "turnover": "tov",
}
_STAT = "|".join(sorted(COUNTS, key=len, reverse=True))
MOST = r"most|highest|best|top|leading|leads?|leaders?|leader|greatest|biggest|largest|longest|strongest|better|more|higher|elite|max(?:imum)?|tall(?:est|er)|old(?:est|er)|heav(?:iest|ier)|fast(?:est|er)|number one"
LEAST = r"fewest|lowest|least|smallest|fewer|lower|less|min(?:imum)?|short(?:est|er)|young(?:est|er)|light(?:est|er)|slow(?:est|er)"
WORST = r"worst|weakest|poorest|worse|bad(?:ly)?"
SUPERLATIVE = rf"{MOST}|{LEAST}|{WORST}|who (?:has|had|made|scored|took|grabbed|dunked|leads?|led)"
SINGLE = r"(?:in|for) (?:a|one|any|his|their) (?:single )?game|single[- ]game|season[- ]?(?:high|best|low)s?|career[- ]high|best (?:game|performance|night)s?|(?:highest|biggest|top)[- ]scoring game|game[- ]high|one night"
TOTAL = r"total(?:s|led)?|in all|altogether|overall|combined|whole season|entire season"
AVERAGE = r"per game|averag\w*|a game|a night|ppg|rpg|apg|mpg|on average"
TOP = 8
LIMITS = re.compile(
    r"(?P<stat>\b(?:ratings?|rates?|usage|scores?|shooting|efficiency|minus|pie|ratio|turnover)\b)(?: percentage)?\s+(?:of |is |that is )?(?P<cmp>at least|more than|over|above|better than|higher than|under|below|less than|lower than)\s+(?P<n>-?\d+(?:\.\d+)?)\s*%?",
    re.I,
)
AGE_WORDS = re.compile(
    r"\b(?:aged?|between)?\s*(?:(?:under|younger than|below|over|older than|above|less than|more than)\s+(?:the age of\s+)?)?\d{2}(?:\s*(?:to|-|and)\s*\d{2})?\s*(?:years?(?:[- ]old)?)?\s*(?:or|and)\s+(?:younger|older|under|over)\b"
    r"|\b(?:younger|older) than \d{2}\b|\b(?:under|over)\s+\d{2}\b(?!\s*(?:%|percent|points?|rebounds?|assists?|steals?|blocks?|threes?|turnovers?|minutes?|games?))|\baged? \d{2}(?:\s*(?:to|-|and)\s*\d{2})?\b",
    re.I,
)


@dataclass
class Query:
    text: str
    players: list[dict] = field(default_factory=list)
    teams: list[dict] = field(default_factory=list)
    roster: list[dict] = field(default_factory=list)  # only players of these teams
    opponents: list[dict] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)  # the slice of games, in words
    home: bool | None = None
    won: bool | None = None
    months: set[int] | None = None
    day: tuple[int, int] | None = None  # month, day
    last: int | None = None
    first: int | None = None
    overtime: bool = False
    rookies: bool = False
    roles: list[str] = field(default_factory=list)
    conference: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    thresholds: list[tuple[str, str, float]] = field(default_factory=list)  # ("reb", ">=", 10)
    percents: list[tuple[str, str, float]] = field(default_factory=list)  # ("three_point_pct", ">=", 40)
    limits: list[tuple[str, float]] = field(default_factory=list)  # on the first statistic: (">", 10)
    low: str = ""  # the question without names

    @property
    def sliced(self) -> bool:
        return bool(self.opponents or self.home is not None or self.won is not None or self.months or self.day or self.last or self.first)


@dataclass
class Fact:
    title: str
    answer: str
    detail: str
    entity: str = "league"
    player_ids: list[int] = field(default_factory=list)
    team_ids: list[int] = field(default_factory=list)
    table: dict | None = None  # {"columns": [...], "rows": [[...]]}
    plan: list[str] = field(default_factory=list)

    def source(self, season: str) -> dict:
        return {
            "kind": "computed", "entity": self.entity, "season": season, "title": self.title, "content": f"{self.answer} {self.detail}".strip(),
            "player_ids": self.player_ids, "team_ids": self.team_ids, "similarity": None,
        }


def ids_of(items) -> list[int]:
    return [i["player_id"] if "player_id" in i else i["nba_team_id"] for i in items]


# ------------------------------------------------------------------ reading

def _number(word: str) -> int:
    return WORDS[word.lower()] if word.lower() in WORDS else int(word)


def game_thresholds(low: str) -> list[tuple[str, str, float]]:
    """"40-point games", "20 point 10 rebound games", "scored 35 or more"."""
    found = []
    for m in re.finditer(rf"(?P<cmp>at least|more than|over|above|under|fewer than|less than|exactly)?\s*(?P<n>\d+(?:\.\d+)?)(?P<plus>\+| or more| or fewer| or less)?[- ]?(?P<stat>{_STAT})s?\b", low, re.I):
        word, plus = (m["cmp"] or "").lower(), m["plus"] or ""
        if word in ("more than", "over", "above"):
            op = ">"
        elif word in ("under", "fewer than", "less than"):
            op = "<"
        elif word == "exactly":
            op = "=="
        else:
            op = "<=" if "fewer" in plus or "less" in plus else ">="
        # "more than 25 points and 5 assists": the second number keeps the comparison.
        if not word and not plus and found and re.search(r"(?:and|,|plus)\s*$", low[: m.start()].rstrip() + " "):
            op = found[-1][1]
        found.append((COUNTS[m["stat"].lower()], op, float(m["n"])))
    if not found and (m := re.search(r"\b(?:scor\w+|dropp?\w*|put up)\s+(at least|more than|over)?\s*(\d+)(\+| or more)?\b(?!\s*(?:%|percent|games?))", low, re.I)):
        found.append(("points", ">" if (m[1] or "").lower() in ("more than", "over") else ">=", float(m[2])))
    return found


def _blank(text: str, word: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", " " * len(word), text, flags=re.I)


def parse(question: str, db) -> Query:
    teams = data.team_list(db)
    records = teams.to_dict("records")
    folk = data.people(db)[["player_id", "full_name", "points"]].to_dict("records")
    named, rest = find_teams(question, records)
    for t in records:  # abbreviations in capitals: BOS, OKC
        if t["nba_team_id"] not in ids_of(named) and re.search(rf"\b{t['abbreviation']}\b", rest):
            named.append({"nba_team_id": t["nba_team_id"], "full_name": t["full_name"]})
            rest = _blank(rest, t["abbreviation"])
    q = Query(question, players=find_players(rest, folk))
    low = rest
    for p in q.players:  # names must not be read as statistics: "Trae Young" is not an age
        for word in p["full_name"].split():
            low = _blank(_blank(low, word), normalize_name(word))
    q.low = low
    _place_teams(q, question, named, teams)
    _read_slice(q)
    q.roles = [r for r, words in ROLES.items() if has(words, low)]
    if has(BIG_MEN, low):
        q.roles = ["Center", "Forward"]
    q.conference = "East" if has(r"east|eastern", low) else "West" if has(r"west|western", low) else None
    # "net rating above 10", "usage over 30%": a limit on a statistic, not an age.
    for m in LIMITS.finditer(low):
        word = (m["cmp"] or "").lower()
        op = ">" if word in ("more than", "over", "above", "better than", "higher than") else "<" if word in ("under", "below", "less than", "lower than") else ">="
        q.limits.append((op, float(m["n"])))
    if q.limits:
        low = q.low = LIMITS.sub(lambda m: m["stat"] + " " * (len(m.group()) - len(m["stat"])), low)
    ages = re.sub(r"\byoung(?:est|er)?\b|\bold(?:est|er)\b", " ", low, flags=re.I) if has(r"youngest|oldest|younger,|older,|who is (?:younger|older)", low) else low
    q.min_age, q.max_age = find_ages(find_thresholds(ages)[1])
    if m := re.search(r"\b(\d{2}) (?:years old )?or (younger|older)\b|\baged? (\d{2})\b", low, re.I):
        if m[3]:
            q.min_age = q.max_age = int(m[3])
            if re.search(r"or younger", low, re.I):
                q.min_age = None
            if re.search(r"or older", low, re.I):
                q.max_age = None
    # What was read as an age group must not be read again as a direction or a statistic.
    low = q.low = AGE_WORDS.sub(lambda m: " " * len(m.group()), low)
    q.rookies = bool(has(r"rookies?|first[- ]year players?", low))
    q.percents = [t for t in find_thresholds(low)[0] if t[0].endswith("_pct")]
    q.thresholds = [] if q.percents and not re.search(rf"\d+\+?[- ]?(?:or more )?(?:{_STAT})\b", low, re.I) else game_thresholds(low)
    q.metrics = find_metrics(low, PLAYER_METRICS)
    return q


PRONOUNS = r"he|him|she|they|them|it|this player|that player|the same player|this team|that team"
POSSESSIVES = r"his|her|their|its"
LEAD = re.compile(r"^\s*(?:and|but|ok|okay|so)?[,\s]*(?:what|how) about\s+|^\s*(?:and|but)\s+", re.I)


def standalone(question: str, previous: str | None, db) -> str:
    """A follow-up rewritten so that it can be understood on its own.

    "How many points does he average at home?" after a question about Curry names Curry;
    "What about Lillard?" repeats the last question for Lillard; "And on the road?" repeats it
    for another slice of games.
    """
    if not previous:
        return question
    before, now = parse(previous, db), parse(question, db)
    old = before.players + before.teams + before.roster
    new = now.players + now.teams + now.roster + now.opponents
    lead = LEAD.search(question)
    rest = question[lead.end():].strip(" ?.") if lead else ""
    if lead and new and not now.metrics and len(old) == 1 and len(rest.split()) <= 5 and not now.opponents:
        # The same question about someone else.
        return _rename(previous, old[0]["full_name"], new[0]["full_name"], before, db)
    if lead and not new and rest:
        if now.metrics:  # "and rebounds?": the same subject, another statistic
            names = " and ".join(p["full_name"] for p in old)
            return f"{names} {rest}{where_words(before)}" if names else question
        if now.sliced:  # "and on the road?": the same question, other games
            if before.thresholds and not before.sliced:
                return f"{previous.rstrip(' ?.')} {rest}?"
            names = " and ".join(p["full_name"] for p in old)
            stats = " and ".join(m.label.lower() for m in before.metrics[:2]) or ("record" if before.teams else "average")
            return f"{names} {stats} {rest}" if names else question
    if new or not old:
        return question
    if len(old) > 1 and has(r"taller|older|younger|heavier|better|more|who (?:is|has|scores?|averages?)|which one|shorter", question):
        return f"{question.rstrip(' ?.')}, {' or '.join(p['full_name'] for p in old)}?"
    names = " and ".join(p["full_name"] for p in old)
    out = re.sub(rf"\b(?:{POSSESSIVES})\b", f"{names}'s", question, flags=re.I)
    return re.sub(rf"\b(?:{PRONOUNS})\b", names, out, count=1, flags=re.I) if out == question else out


def _rename(question: str, old: str, new: str, before: Query, db) -> str:
    """Replace however the old name was written with the new one."""
    words = sorted({old, *old.split(), normalize_name(old), *normalize_name(old).split()}, key=len, reverse=True)
    if before.teams or before.roster:
        row = data.team_list(db).loc[(before.teams + before.roster)[0]["nba_team_id"]]
        words = [row.full_name, row.nickname, row.city, row.abbreviation]
    pattern = "|".join(rf"(?<!\w){re.escape(w)}(?!\w)" for w in words if len(w) > 2)
    out, n = re.subn(rf"(?:{pattern})(?:\s+(?:{pattern}))*", new, question, count=1, flags=re.I)
    return out if n else f"{new} {question}"


def _place_teams(q: Query, question: str, named: list[dict], teams: pd.DataFrame) -> None:
    """Opponent, roster or subject, by the words in front of the name."""
    for t in named:
        row = teams.loc[t["nba_team_id"]]
        spot = re.search("|".join(rf"\b{re.escape(n)}\b" for n in (row.full_name, row.nickname, row.city, row.abbreviation)), question)
        before = question[: spot.start()].lower() if spot else ""
        if re.search(r"\b(?:against|versus|vs\.?|facing|faced)(?: the)?\s*$", before) or ((q.teams or q.players) and re.search(r"\b(?:beat|hosted|visited|over|played?|playing|to|and|or)(?: the)?\s*$", before) and q.players):
            q.opponents.append(t)
        elif not has(r"teams?", q.low) and has(r"who|players?|guards?|forwards?|centers?|scorers?|shooters?|rebounders?|passers?|defenders?|rookies?", q.low) and not has(r"who (?:won|beat|did)|record|won more|beat|duos?|pair\w*|chemistry|combination\w*|roster", q.low):
            q.roster.append(t)
        else:
            q.teams.append(t)
    if q.players:  # "Jokic on the Nuggets" is still a question about Jokic
        if not q.opponents and named and has(r"against|versus|vs|facing|when .*play\w*", q.low):
            q.opponents = list(named)
        q.teams, q.roster = [], []


def _read_slice(q: Query) -> None:
    low = q.low
    home, away = has(r"at home|home games?|home records?|home court|hosted|when hosting", low), has(r"on the road|away(?: from home)?|road (?:games?|records?)|visiting", low)
    if home and not away:
        q.home = True
        q.scope.append("at home")
    elif away and not has(r"home", low.lower().replace("away from home", "")):
        q.home = False
        q.scope.append("on the road")
    if has(r"(?:in|during) wins|when (?:\w+ ){0,5}(?:win|wins|won)|winning games|in victories", low):
        q.won = True
        q.scope.append("in wins")
    elif has(r"(?:in|during) loss(?:es)?|when (?:\w+ ){0,5}(?:lose|loses|lost)|losing games|in defeats", low):
        q.won = False
        q.scope.append("in losses")
    names = "|".join(MONTHS)
    if m := re.search(rf"\b(after|since|before|until|through)\s+({names})\b", low, re.I):
        at, word = SEASON_MONTHS.index(MONTHS[m[2].lower()]), m[1].lower()
        q.months = set(SEASON_MONTHS[at + (word == "after"):] if word in ("after", "since") else SEASON_MONTHS[: at + (word in ("until", "through"))])
        q.scope.append(f"{word} {m[2].title()}")
    elif m := re.search(rf"\b(?:({names})\s+(\d{{1,2}})(?:st|nd|rd|th)?|(\d{{1,2}})(?:st|nd|rd|th)?(?: of)? ({names}))\b", low, re.I):
        name, day = (m[1], m[2]) if m[1] else (m[4], m[3])
        q.day = (MONTHS[name.lower()], int(day))
        q.scope.append(f"on {day} {name.title()}")
    elif has(r"christmas", low):
        q.day = (12, 25)
        q.scope.append("on 25 December")
    elif found := [m for m in MONTHS if re.search(rf"\b{m}\b", low, re.I)]:
        q.months = {MONTHS[m] for m in found}
        q.scope.append("in " + " and ".join(m.title() for m in found))
    number = rf"(\d+|{'|'.join(WORDS)})"
    if m := re.search(rf"\b(?:last|past|final|previous|recent)\s+{number}\s+(?:\w+ )?(?:games?|matches|outings)\b", low, re.I):
        q.last = _number(m[1])
        q.scope.append(f"in the last {q.last} games")
    elif m := re.search(rf"\b(?:first|opening)\s+{number}\s+(?:\w+ )?games?\b", low, re.I):
        q.first = _number(m[1])
        q.scope.append(f"in the first {q.first} games")
    elif has(r"last game|most recent game|latest game", low):
        q.last = 1
        q.scope.append("in the last game")
    q.overtime = bool(has(r"overtimes?|ot", low))
    if q.opponents:
        q.scope.append("against the " + " and ".join(t["full_name"] for t in q.opponents))


# ------------------------------------------------------------------ slices and sums

def slice_games(frame: pd.DataFrame, q: Query, group: str) -> pd.DataFrame:
    if q.opponents:
        frame = frame[frame.opp.isin(ids_of(q.opponents))]
    if q.home is not None:
        frame = frame[frame.home == q.home]
    if q.won is not None:
        frame = frame[frame.won == q.won]
    if q.months:
        frame = frame[frame.game_date.dt.month.isin(q.months)]
    if q.day:
        frame = frame[(frame.game_date.dt.month == q.day[0]) & (frame.game_date.dt.day == q.day[1])]
    if q.last:  # rows are in date order
        frame = frame.groupby(group).tail(q.last)
    if q.first:
        frame = frame.groupby(group).head(q.first)
    return frame


def sum_players(db, q: Query) -> pd.DataFrame:
    frame = slice_games(data.box_scores(db), q, "player_id")
    columns = [*data.SUMS, "plus_minus", "game_score", "double_doubles", "triple_doubles"]
    sums = frame.groupby("player_id")[columns].sum().astype(float)
    sums["gp"] = frame.groupby("player_id").size()
    return sums.join(data.people(db).drop(columns=["points", "gp", "player_id"]), how="inner")


def sum_teams(db, q: Query) -> pd.DataFrame:
    frame = slice_games(data.team_games(db), q, "team")
    sums = frame.groupby("team")[[*data.SUMS, *[f"a_{c}" for c in data.SUMS], "margin"]].sum().astype(float)
    sums["won"] = frame.groupby("team")["won"].sum()
    sums["gp"] = frame.groupby("team").size()
    close = frame[frame.margin.abs() <= 5]
    sums["close_games"], sums["close_wins"] = close.groupby("team").size(), close.groupby("team")["won"].sum()
    return sums.join(data.team_list(db)[["full_name", "conference", "nickname"]], how="inner")


def eligible(sums: pd.DataFrame, metric: Metric | None, q: Query, strict: bool = True) -> pd.DataFrame:
    """Players inside the question's group, with enough games or attempts to be ranked."""
    out = sums
    if q.roster:
        out = out[out.team.isin(ids_of(q.roster))]
    if q.conference and not q.teams:
        out = out[out.conference == q.conference]
    if q.roles:
        out = out[[any(r in p for r in q.roles) for p in out.position]]
    if q.min_age is not None:
        out = out[out.age >= q.min_age]
    if q.max_age is not None:
        out = out[out.age <= q.max_age]
    if q.rookies:
        out = out[out.experience == 1]
    if not strict or metric is None or not len(sums):
        return out
    part = min(1.0, sums.gp.max() / 82)  # a slice of the season needs a slice of the attempts
    if metric.need:
        column, least = metric.need
        out = out[out[column] >= least * part]
    elif metric.key not in ("height", "weight", "age", "experience", "double_doubles", "triple_doubles", "games"):
        out = out[(out.gp >= max(1, round(20 * part))) & (out.minutes / out.gp >= 12)]
    return out


def descending(q: Query, metric: Metric) -> bool:
    if has(LEAST, q.low):
        return False
    if has(WORST, q.low):
        return metric.lower
    if has(r"best|better|top|elite", q.low):
        return not metric.lower
    if has(MOST, q.low):
        return True
    return metric.key not in ("def_rating", "opp_points", "defended_fg_pct", "defended_fg_diff")


def wants_total(q: Query, metric: Metric) -> bool:
    if metric.total is None or has(AVERAGE, q.low):
        return False
    if has(TOTAL, q.low):
        return True
    past = r"made|scored|grabbed|had|recorded|dished|took|played|attempted|hit|got|committed|collected"
    if has(rf"(?:who|which (?:\w+ ){{1,2}})\s*(?:{past})", q.low) and has(f"{MOST}|{LEAST}", q.low):
        return True
    return bool(has(r"how many (?:\w+[ -]){0,3}(?:did|has|have) .*(?:make|made|score|grab|record|have|had|get|collect|commit|take|attempt|play|block|steal|dish)\w*", q.low))


# ------------------------------------------------------------------ in words

def where_words(q: Query) -> str:
    return f" {' '.join(q.scope)}" if q.scope else ""


def group_words(q: Query) -> str:
    out = []
    if q.roles:
        out.append(" and ".join(r.lower() + "s" for r in q.roles))
    if q.conference:
        out.append(f"in the {q.conference}ern Conference")
    if q.max_age is not None and q.max_age == q.min_age:
        out.append(f"aged {q.max_age}")
    else:
        if q.max_age is not None:
            out.append(f"aged {q.max_age} or younger")
        if q.min_age is not None:
            out.append(f"aged {q.min_age} or older")
    if q.rookies:
        out.append("in their first season")
    if q.roster:
        out.append("on the " + " and ".join(t["full_name"] for t in q.roster))
    return ("" if not out or q.roles else "players ") + ", ".join(out).removesuffix(",")


def describe_plan(q: Query, *steps: str) -> list[str]:
    out = []
    if q.players:
        out.append("Players: " + ", ".join(p["full_name"] for p in q.players))
    if q.teams:
        out.append("Teams: " + ", ".join(t["full_name"] for t in q.teams))
    if group_words(q):
        out.append("Group: " + group_words(q))
    if q.scope:
        out.append("Games: " + ", ".join(q.scope))
    return out + [s for s in steps if s]
