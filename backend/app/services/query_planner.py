"""Reads a question and decides how to look the answer up.

Vector search is good at meaning and bad at arithmetic: to an embedding "under 25" and "over
25" look almost the same. So everything exact in a question (names, teams, positions, ages,
thresholds, "best"/"most") becomes a structured constraint, and only what is left is searched
by meaning. Rules rather than a language model: the plan is instant, free, the same every
time, testable, and can be shown to the user.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from app.services.text_utils import normalize_name

YOUNG_MAX_AGE, VETERAN_MIN_AGE = 24, 33


@dataclass
class Plan:
    intent: str = "open"  # open, similar, ranking, team_ranking, lookup, out_of_scope
    kinds: list[str] = field(default_factory=list)
    players: list[dict] = field(default_factory=list)  # {"player_id", "full_name"}
    teams: list[dict] = field(default_factory=list)  # {"nba_team_id", "full_name"}
    roles: list[str] = field(default_factory=list)
    min_age: int | None = None
    max_age: int | None = None
    thresholds: list[tuple[str, str, float]] = field(default_factory=list)  # ("rebounds", ">=", 10)
    skills: list[str] = field(default_factory=list)
    order: tuple[str, bool] | None = None  # (team metric, descending)
    reason: str = ""

    def summary(self) -> list[str]:
        """The plan in words, shown next to the answer."""
        out = []
        if self.players:
            out.append("Players: " + ", ".join(p["full_name"] for p in self.players))
        if self.teams:
            out.append("Teams: " + ", ".join(t["full_name"] for t in self.teams))
        if self.roles:
            out.append("Position: " + " or ".join(self.roles))
        if self.min_age is not None:
            out.append(f"Age {self.min_age} or older")
        if self.max_age is not None:
            out.append(f"Age {self.max_age} or younger")
        out += [f"{stat.replace('_', ' ')} {op} {value:g}{'%' if stat.endswith('pct') else ''}" for stat, op, value in self.thresholds]
        if self.intent == "ranking" and self.skills:
            out.append("Ranked by " + ", ".join(SKILL_LABELS.get(s, s) for s in self.skills))
        if self.order:
            out.append(f"Teams ranked by {self.order[0].replace('_', ' ')}, {'highest' if self.order[1] else 'lowest'} first")
        if self.intent == "similar":
            out.append("Nearest statistical profiles")
        if self.kinds:
            out.append("Looking in: " + ", ".join(k.replace("_", " ") for k in self.kinds))
        return out


SKILL_LABELS = {"three_point_attempts": "threes attempted", "three_point_shrunk": "three-point accuracy", "free_throw_shrunk": "free throw accuracy", "field_goal_pct": "field goal percentage"}

# Words in a question that point at a measurable skill.
SKILL_WORDS = [
    (r"rim protect\w*|shot[- ]?block\w*|blocks?|blockers?|swat\w*", ["blocks"]),
    (r"rebound\w*|boards", ["rebounds"]),
    (r"playmak\w*|pass(?:es|ers?|ing)?|assists?|facilitat\w*", ["assists"]),
    (r"steals?|perimeter defen\w*", ["steals"]),
    (r"turnovers?|turns? the ball over", ["turnovers"]),
    (r"(?<!perimeter )(?:defen[cs]\w*|defenders?)", ["steals", "blocks"]),
    (r"threes|3s|three[- ]point\w*|3[- ]?point\w*|shooters?|shoot|spacing", ["three_point_attempts", "three_point_shrunk"]),
    (r"scor(?:e|es|er|ers|ing)|points", ["points"]),
    (r"free throws?", ["free_throw_shrunk"]),
    (r"efficien\w*|finish\w*", ["field_goal_pct"]),
]
ROLES = {"Guard": r"guards?|point guards?|shooting guards?|backcourt", "Forward": r"forwards?|wings?", "Center": r"cent(?:er|re)s?|bigs"}
BIG_MEN = r"big (?:men|man|guys)|bigs"
NUMBER_STATS = {
    "points": r"points?|ppg|pts", "rebounds": r"rebounds?|rpg|boards", "assists": r"assists?|apg", "steals": r"steals?", "blocks": r"blocks?",
    "turnovers": r"turnovers?", "minutes": r"minutes?|mpg", "games_played": r"games",
}
PERCENT_STATS = [("three_point_pct", r"threes?|3s|three[- ]point\w*|3[- ]?point\w*|deep"), ("free_throw_pct", r"free[- ]throws?|the (?:free throw )?line"), ("field_goal_pct", r"the field|field goals?")]
AT_LEAST = r"at least|minimum(?: of)?|no (?:less|fewer) than|>="
MORE = r"more than|over|above|better than|exceed\w*|>"
AT_MOST = r"at most|maximum(?: of)?|no more than|up to|<="
LESS = r"less than|fewer than|under|below|<"
COMPARE = rf"(?P<ge>{AT_LEAST})|(?P<gt>{MORE})|(?P<le>{AT_MOST})|(?P<lt>{LESS})"

SIMILAR = r"similar|like|comparable|resembl\w*|replace\w*|alternatives?|same (?:style|profile)"
MATCHUPS = r"(?:who|which \w+|that) (?:guards?|guarded|defends?|defended|stops?|stopped)|guarded by|defended by|match[- ]?ups?|slow(?:s|ed)? down|shut(?:s)? down|struggl\w* (?:to score )?(?:against|with)|gave \w+(?: \w+)? (?:the most |the biggest )?(?:trouble|problems)|trouble|hard(?:est)? (?:time )?to (?:guard|face)|toughest defenders?|held"
PAIRS = r"duos?|pair(?:s|ing|ings)?|two[- ]man|tandems?|chemistry|together|combinations?|combos?"
SHOTS = r"corner|mid[- ]?range|at the rim|near the rim|in the paint|restricted area|above the break|shot (?:chart|zones?|locations?|selection|profile)|where (?:does|do|did|is)|from where|shots?"
FORM = r"form|lately|recent(?:ly)?|last (?:\d+ |few )?games|hot|cold|streak\w*|slump\w*|finish\w* the (?:season|year)|end of the (?:season|year)|down the stretch"
GAMES = r"games?|beat|beaten|won against|lost to|lose to|played|play(?:ed)? against|results?|scores? of|versus|vs\.?|against|head[- ]to[- ]head"
BEST = r"best|top|leading|leads?|leaders?|most|highest|elite|greatest|strongest|worst|lowest|fewest|least"
WORST = r"worst|lowest|fewest|least|weakest|poorest"
# metric, words, higher is better
TEAM_METRICS = [
    ("def_rating", r"defen[cs]\w*|defend\w*", False), ("off_rating", r"offen[cs]\w*|scor\w*|efficien\w*", True), ("wins", r"w[io]ns?|record", True),
    ("three_pct", r"(?:three|3)[- ]?point (?:percentage|accuracy)|accurate", True), ("threes", r"threes|3s|three[- ]?point\w*|3[- ]?point\w*", True), ("pace", r"pace|fast\w*|tempo", True),
    ("rebounds", r"rebound\w*", True), ("assists", r"assist\w*|passing", True), ("turnovers", r"turnovers?", False),
]
TEAM_ALIASES = {"sixers": "76ers", "wolves": "Timberwolves", "cavs": "Cavaliers", "mavs": "Mavericks", "blazers": "Trail Blazers"}
PLAYER_ALIASES = {"sga": "Shai Gilgeous-Alexander", "wemby": "Victor Wembanyama", "greek freak": "Giannis Antetokounmpo", "steph": "Stephen Curry", "kd": "Kevin Durant", "cp3": "Chris Paul", "king james": "LeBron James"}
OTHER_TOPICS = r"salar(?:y|ies)|contracts?|paid|cap space|wnba|ncaa|college|euroleague|olympic\w*|mvp|all[- ]star\w*|awards?|championships?|finals|playoffs?|draft\w*|injur\w*|next (?:year|season)|will (?:win|be)|coach\w*"
# Names that are also ordinary words or cities in basketball questions.
STOP_NAMES = {"young", "will", "best", "which", "who", "what", "houston", "jordan", "west", "love", "max", "guards", "centers", "players", "compare", "show", "find", "league"}
SUFFIXES = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v"}


def has(pattern: str, value: str):
    return re.search(rf"\b(?:{pattern})\b", value, re.I)


def base_name(full_name: str) -> str:
    return " ".join(w for w in normalize_name(full_name).split() if w not in SUFFIXES)


def find_teams(question: str, teams: list[dict]) -> tuple[list[dict], str]:
    """Teams mentioned, and the question with those words blanked so they are not read as names."""
    for alias, nickname in TEAM_ALIASES.items():
        question = re.sub(rf"\b{alias}\b", nickname, question, flags=re.I)
    found, left = [], question
    cities = [t["city"] for t in teams]
    for t in teams:
        names = [t["full_name"], t["nickname"]] + ([t["city"]] if cities.count(t["city"]) == 1 else [])
        for name in names:
            # Nicknames such as Heat, Magic or Jazz are ordinary words unless capitalised.
            if match := re.search(rf"\b{re.escape(name)}\b", left):
                found.append((match.start(), t))
                left = re.sub(rf"\b{re.escape(name)}\b", lambda m: " " * len(m.group()), left)
    found.sort(key=lambda item: item[0])
    unique = {t["nba_team_id"]: {"nba_team_id": t["nba_team_id"], "full_name": t["full_name"]} for _, t in found}
    return list(unique.values()), left


# Last names that are ordinary words; they only count as names when capitalised.
COMMON = {"brown", "green", "white", "young", "black", "bridges", "banks", "brooks", "wells", "battle", "strong", "love", "rose", "grant", "price", "hunter", "walker", "porter", "holiday", "smart", "house", "wood", "jones", "little", "small", "champagnie", "point", "points", "fears", "sharpe", "council", "boston", "washington", "houston", "jackson", "jordan", "dallas", "miles", "games", "christmas", "guard", "center", "short", "thomas", "paul", "will", "mark", "chris", "mike", "isaiah", "player", "dunn", "dunns", "cook", "fultz", "mann", "reed", "ball", "branch", "bones", "precious", "royce", "simpson", "payne", "walter"}


def find_players(question: str, people: list[dict], limit: int = 6) -> list[dict]:
    """Players mentioned by full name, or by first or last name (the best scorer wins); misspellings are forgiven."""
    for alias, name in PLAYER_ALIASES.items():
        question = re.sub(rf"\b{alias}\b", name, question, flags=re.I)
    plain = normalize_name(question)
    found, taken = [], []
    for person in sorted(people, key=lambda p: -len(p["full_name"])):
        if match := re.search(rf"(?<!\w){re.escape(base_name(person['full_name']))}(?!\w)", plain):
            if not any(a <= match.start() < b for a, b in taken):
                found.append((match.start(), person))
                taken.append(match.span())
    used = {word for _, p in found for word in normalize_name(p["full_name"]).split()}
    by_word: dict[str, list[dict]] = {}
    for p in people:
        for word in base_name(p["full_name"]).split():
            by_word.setdefault(word, []).append(p)
    for match in re.finditer(r"[^\W\d_][\w'’\-]*", question):
        word = match.group()
        key = re.sub(r"['’]s?$", "", normalize_name(word))
        if len(key) < 4 or key in used or key in STOP_NAMES:
            continue
        capital, first = word[0].isupper(), match.start() == 0
        matches = by_word.get(key, [])
        # Without a capital letter only unusual names count; the first word of a sentence proves nothing.
        if matches and not capital and (len(key) < 5 or key in COMMON):
            continue
        if matches and first and len(matches) > 1 and key in COMMON:
            continue
        if not matches and capital and not first and len(key) >= 5:
            close = difflib.get_close_matches(key, [w for w in by_word if len(w) >= 5], n=1, cutoff=0.84)
            matches = by_word[close[0]] if close else []
        if not matches:
            continue
        best = max(matches, key=lambda p: p["points"] or 0)
        found.append((match.start(), best))
        used.update(normalize_name(best["full_name"]).split())
    found.sort(key=lambda item: item[0])
    unique = {p["player_id"]: {"player_id": p["player_id"], "full_name": p["full_name"]} for _, p in found}
    return list(unique.values())[:limit]


def find_thresholds(question: str) -> tuple[list[tuple[str, str, float]], str]:
    """"at least 10 rebounds and 3 assists" -> two constraints; returns the rest of the text too."""
    found, left = [], question
    stat_words = "|".join(f"(?P<{name}>{words})" for name, words in NUMBER_STATS.items())
    pattern = re.compile(rf"(?:(?:{COMPARE})\s*)?(?P<n>\d+(?:\.\d+)?)(?P<plus>\+| or more| or fewer)?\s*(?:{stat_words})\b", re.I)
    inherited = None
    for m in pattern.finditer(question):
        before = question[max(0, m.start() - 25):m.start()]
        # "last 10 games" is a window, not a filter.
        if m["games_played"] and not any(m[k] for k in ("ge", "gt", "le", "lt", "plus")):
            continue
        op = next((o for k, o in (("ge", ">="), ("gt", ">"), ("le", "<="), ("lt", "<")) if m[k]), None)
        if m["plus"]:
            op = "<=" if "fewer" in m["plus"] else ">="
        if op is None:
            # "... and 3 assists" keeps the comparison before it; "averages 20 points" means at least.
            op = inherited if inherited and re.search(r"\b(and|,|plus)\s*$|,\s*$", before) else ">=" if re.search(r"averag\w*\s*$", before, re.I) else None
        if op is None:
            continue
        inherited = op
        found.append((next(name for name in NUMBER_STATS if m[name]), op, float(m["n"])))
        left = left.replace(m.group(), " " * len(m.group()), 1)
    for m in re.finditer(rf"(?:(?:{COMPARE})\s*)?(?P<n>\d+(?:\.\d+)?)\s*(?:%|percent)\+?\s*(?P<rest>(?:from|on|of|in)?\s*[\w \-]{{0,30}})", question, re.I):
        around = m["rest"] + " " + question[max(0, m.start() - 40):m.start()]
        stat = next((name for name, words in PERCENT_STATS if has(words, m["rest"])), None) or next((name for name, words in PERCENT_STATS if has(words, around)), "field_goal_pct")
        op = next((o for k, o in (("ge", ">="), ("gt", ">"), ("le", "<="), ("lt", "<")) if m[k]), ">=")
        found.append((stat, op, float(m["n"])))
        left = left.replace(m.group(), " " * len(m.group()), 1)
    return found, left


def find_ages(question: str) -> tuple[int | None, int | None]:
    if m := re.search(r"\b(?:aged?|between)\s+(\d{2})\s*(?:to|-|–|and)\s*(\d{2})\b", question, re.I):
        return int(m[1]), int(m[2])
    low = high = None
    if m := re.search(r"\b(\d{2})\s+(?:or|and)\s+(younger|under|older|over)\b", question, re.I):
        return (None, int(m[1])) if m[2].lower() in ("younger", "under") else (int(m[1]), None)
    if m := re.search(r"\b(?:under|younger than|below|less than|u-?)\s*(?:the age of )?(\d{2})\b(?!\s*%)", question, re.I):
        high = int(m[1]) - 1
    if m := re.search(r"\b(?:over|older than|above|more than)\s*(?:the age of )?(\d{2})\b(?!\s*%)", question, re.I):
        low = int(m[1]) + 1
    if low is None and high is None:
        if has(r"young|younger|youngest|youth|prospects?|rising", question):
            high = YOUNG_MAX_AGE
        elif has(r"veterans?", question):
            low = VETERAN_MIN_AGE
    return low, high


def find_skills(question: str) -> list[str]:
    # "three-point" contains "point"; without this it would also count as scoring.
    plain = re.sub(r"\b(?:three|3)[- ]?point\w*", "threes", question, flags=re.I)
    return list(dict.fromkeys(f for words, features in SKILL_WORDS if has(words, plain) for f in features))


def outside_season(question: str, season: str) -> str | None:
    """A season or year in the question that the database does not hold."""
    start = int(season[:4])
    allowed = {start, start + 1}
    for m in re.finditer(r"\b((?:19|20)\d{2})(?:\s*[-/–]\s*(\d{2,4}))?\b", question):
        year = int(m[1])
        if m[2]:
            if year != start:
                return m.group()
        elif year not in allowed:
            return m.group()
    return None


def make_plan(question: str, season: str, people: list[dict], teams: list[dict]) -> Plan:
    plan = Plan()
    if year := outside_season(question, season):
        plan.intent, plan.reason = "out_of_scope", f"The database covers {season} only, and the question is about {year}."
        return plan
    if topic := has(OTHER_TOPICS, question):
        plan.intent, plan.reason = "out_of_scope", f"The database holds {season} regular season statistics and nothing about \"{topic.group()}\"."
        return plan

    plan.teams, rest = find_teams(question, teams)
    plan.players = find_players(rest, people)
    plan.thresholds, rest = find_thresholds(rest)
    plan.min_age, plan.max_age = find_ages(rest)
    for person in plan.players:  # "Trae Young" is not a request for young players
        if "young" in normalize_name(person["full_name"]).split() and not re.search(r"\b(young|younger) (?:players?|talent)", rest):
            if plan.max_age == YOUNG_MAX_AGE and not re.search(r"\d", rest):
                plan.max_age = None
    plan.skills = find_skills(rest)
    plan.roles = [role for role, words in ROLES.items() if has(words, rest)]
    if has(BIG_MEN, rest):
        plan.roles = list(dict.fromkeys([*plan.roles, "Center", "Forward"]))

    about_teams = bool(has(r"teams?|franchises?|clubs?", rest))
    limits = bool(plan.thresholds or plan.roles or plan.min_age is not None or plan.max_age is not None)

    if plan.players and has(MATCHUPS, rest):
        plan.intent, plan.kinds, plan.roles = "lookup", ["matchups"], []
    elif plan.teams and has(PAIRS, rest):
        plan.intent, plan.kinds = "lookup", ["pairs"]
    elif len(plan.teams) >= 2 and has(GAMES, rest):
        plan.intent, plan.kinds = "lookup", ["game"]
    elif plan.players and has(SIMILAR, rest):
        plan.intent, plan.kinds = "similar", ["player_season"]
    elif plan.players and has(FORM, rest):
        plan.intent, plan.kinds = "lookup", ["form"]
    elif plan.players and has(SHOTS, rest):
        plan.intent, plan.kinds = "lookup", ["shot_profile"]
    elif plan.players and not limits:
        plan.intent, plan.kinds = "lookup", ["player_season"]
    elif about_teams and not plan.players and (metric := next(((m, high) for m, words, high in TEAM_METRICS if has(words, rest)), None)):
        name, higher_better = metric
        more = not has(WORST, rest) if name not in ("turnovers",) else bool(has(r"most|highest", rest))
        plan.intent, plan.kinds = "team_ranking", ["team_season"]
        plan.order = (name, more if name == "turnovers" else more == higher_better)
    elif plan.teams and not limits and not has(r"players?|who|guys", rest):
        plan.intent, plan.kinds = "lookup", ["team_season"]
    elif plan.skills or plan.thresholds or limits or plan.teams:
        plan.intent, plan.kinds = "ranking", ["player_season"]
    return plan
