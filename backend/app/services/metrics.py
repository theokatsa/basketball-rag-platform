"""Every statistic the pages show, with the words people use for it.

A metric is calculated from summed rows, so the same definition works for a season, a month,
games against one team or the last five games.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    words: str  # regular expression
    value: Callable  # summed rows -> number
    digits: int = 1
    suffix: str = ""
    lower: bool = False  # lower is better
    total: Callable | None = None  # season total, when that is a question of its own
    need: tuple[str, int] | None = None  # minimum attempts for rankings, over a full season
    season_only: bool = False  # published for the season as a whole, not per game
    unit: str = ""  # "points": used in sentences
    signed: bool = False

    def show(self, value) -> str:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "no data"
        if self.key == "height":
            return f"{int(value) // 12}'{int(value) % 12}\""
        return f"{value:{'+' if self.signed else ''}.{self.digits}f}{self.suffix}"


def ratio(top, bottom, scale=1.0):
    return lambda a: scale * top(a) / bottom(a)


def per_game(column):
    return lambda a: a[column] / a["gp"]


def total(column):
    return lambda a: a[column]


def share(made, tried):
    return lambda a: 100 * a[made] / a[tried]


def _counting(key, label, words, column, **more):
    return Metric(key, label, words, per_game(column), total=total(column), unit=more.pop("unit", label.lower()), **more)


def _season(key, label, words, column=None, **more):
    return Metric(key, label, words, total(column or key), season_only=True, **more)


MADE, TRIED = r"(?:made|makes|make|hit|hits|sank|drained)", r"(?:attempt\w*|taken|takes?|took|tries|shot\b)"
THREE = r"(?<![\w.])(?:three|3)[- ]?(?:point(?:er)?s?|pt|ptr)?s?(?!\w)"

# Order matters: the first pattern that matches a stretch of text claims it.
PLAYER_METRICS = [
    Metric("double_doubles", "Double-doubles", r"double[- ]?doubles?", total("double_doubles"), 0, total=total("double_doubles"), unit="double-doubles"),
    Metric("triple_doubles", "Triple-doubles", r"triple[- ]?doubles?", total("triple_doubles"), 0, total=total("triple_doubles"), unit="triple-doubles"),
    Metric("game_score", "Game Score", r"game[- ]?scores?", per_game("game_score"), total=total("game_score")),
    Metric("plus_minus", "Plus/minus", r"plus[\s/-]*minus|\+/-", per_game("plus_minus"), total=total("plus_minus"), signed=True),
    _season("offense_score", "Offense score", r"(?:offen[cs]\w*) scores?|best offensive players?"), _season("defense_score", "Defense score", r"(?:defen[cs]\w*) scores?|best defen(?:sive players?|ders?)|defen(?:ders?|ds)\b|elite defen\w+"),
    _season("overall_score", "Overall score", r"overall (?:score|rating|player)s?|best (?:all[- ]?round |overall )?players?|best overall"),
    _season("usg_pct", "Usage rate", r"usage(?: rate| percentage)?|usg%?", suffix="%", need=("minutes", 500)),
    _season("ast_to", "Assists per turnover", r"assists?[- ]?(?:to|per|/)[- ]?turnovers?(?: ratio)?", digits=2, need=("minutes", 500)),
    _season("ast_pct", "Assist rate", r"assist (?:rate|percentage|%)", suffix="%", need=("minutes", 500)),
    _season("oreb_pct", "Offensive rebound rate", r"offensive rebound(?:ing)? (?:rate|percentage|%)", suffix="%", need=("minutes", 500)),
    _season("dreb_pct", "Defensive rebound rate", r"defensive rebound(?:ing)? (?:rate|percentage|%)", suffix="%", need=("minutes", 500)),
    _season("reb_pct", "Rebound rate", r"rebound(?:ing)? (?:rate|percentage|%)", suffix="%", need=("minutes", 500)),
    _season("tov_pct", "Turnover rate", r"turnover (?:rate|percentage|%)", lower=True, need=("minutes", 500)),
    _season("defended_fg_diff", "Opponent FG% against their average", r"(?:opponents?|opposing)\W+(?:\w+ ){0,3}(?:worse|below|than usual|vs average)|shot contest\w*|contest\w* shots?", lower=True, need=("defended_fga", 200), signed=True),
    _season("defended_fg_pct", "Opponent FG% when guarding", r"(?:opponents?|opposing)'? ?(?:players? )?(?:field goal|fg|shooting)(?: percentage| %|%)?|defended (?:field goal|fg)\w*(?: percentage| %|%)?|dfg%?", suffix="%", lower=True, need=("defended_fga", 200)),
    _season("def_rating", "Defensive rating", r"defen[cs]ive rating|def(?:ensive)?[ .]?rtg|drtg", lower=True, need=("minutes", 500)),
    _season("off_rating", "Offensive rating", r"offen[cs]ive rating|off?[ .]?rtg|ortg", need=("minutes", 500)),
    _season("net_rating", "Net rating", r"net[- ]?(?:rating|rtg)|net impact", need=("minutes", 500), signed=True),
    _season("pie", "Player impact estimate", r"player impact(?: estimate)?|\bpie\b", suffix="%", need=("minutes", 500)),
    Metric("ts", "True shooting", r"true[- ]?shooting(?: percentage| %|%)?|\bts%?|scoring efficiency|efficient (?:scorers?|shooters?|players?)|efficien\w+", lambda a: 100 * a.points / (2 * (a.fga + 0.44 * a.fta)), suffix="%", need=("fga", 200)),
    Metric("efg", "Effective field goal", r"effective (?:field goal|fg|shooting)(?: percentage| %|%)?|\be?fg%", lambda a: 100 * (a.fgm + 0.5 * a.tpm) / a.fga, suffix="%", need=("fga", 200)),
    Metric("three_pct", "Three-point percentage", rf"{THREE} (?:percentage|accuracy|shooting|shooters?|%)|{THREE}[- ]?%|(?:shoot\w*|shot|accura\w+|percent(?:age)?|%)[\w \-]{{0,25}}(?:from|on|behind) (?:{THREE}|deep|downtown|the arc|beyond the arc|distance)|(?:from|on) (?:{THREE}|deep|downtown|beyond the arc)", share("tpm", "tpa"), suffix="%", need=("tpa", 100)),
    _counting("tpa", "Threes attempted", rf"(?:{THREE} )?{TRIED}[\w \-]{{0,12}} {THREE}|{THREE} {TRIED}", "tpa", unit="threes attempted"),
    _counting("tpm", "Threes made", rf"{MADE}[\w \-]{{0,12}} {THREE}|{THREE} {MADE}|{THREE}", "tpm", unit="threes"),
    Metric("ft_pct", "Free throw percentage", r"free[- ]?throw (?:percentage|accuracy|shooting|shooters?|%)|(?:shoot\w*|percent(?:age)?|accura\w+)[\w \-]{0,20}(?:from the (?:free throw |foul )?line|free throws?)|from the (?:free throw |foul |charity )?(?:line|stripe)|\bft%", share("ftm", "fta"), suffix="%", need=("fta", 75)),
    _counting("fta", "Free throws attempted", rf"free[- ]?throws? {TRIED}|{TRIED}[\w \-]{{0,12}} free[- ]?throws?|(?:gets?|got|goes|went|go) to the (?:free throw |foul )?line|draw\w* (?:the most )?fouls?|fouls? drawn", "fta", unit="free throws attempted"),
    _counting("ftm", "Free throws made", r"free[- ]?throws?", "ftm", unit="free throws"),
    Metric("fg_pct", "Field goal percentage", r"field[- ]?goal (?:percentage|accuracy|%)|\bfg%|shooting (?:percentage|accuracy|splits?)|from the (?:field|floor)", share("fgm", "fga"), suffix="%", need=("fga", 200)),
    _counting("fga", "Field goals attempted", rf"field[- ]?goals? {TRIED}|{TRIED}[\w \-]{{0,12}} (?:field goals?|shots)|shots? (?:per game|attempted|taken)", "fga", unit="shots"),
    _counting("fgm", "Field goals made", r"field[- ]?goals?|baskets?|buckets? made", "fgm", unit="field goals"),
    _counting("oreb", "Offensive rebounds", r"offensive (?:rebound\w*|boards?|glass)", "oreb"), _counting("dreb", "Defensive rebounds", r"defensive (?:rebound\w*|boards?|glass)", "dreb"),
    _counting("rebounds", "Rebounds", r"rebound\w*|\brpg\b|\bboards?\b", "reb"), _counting("assists", "Assists", r"assist\w*|\bapg\b|\bdimes?\b|playmak\w*|\bpass(?:es|ers?|ing)\b", "ast"),
    _counting("steals", "Steals", r"steals?\b|\bspg\b", "stl"), _counting("blocks", "Blocks", r"blocks?\b|blocked|\bbpg\b|shot[- ]?block\w*|rim protect\w*", "blk"),
    _counting("turnovers", "Turnovers", r"turnovers?|turn(?:s|ed)? (?:the ball |it )?over", "tov", lower=True), _counting("fouls", "Fouls", r"(?:personal )?fouls?\b", "pf", lower=True),
    _counting("minutes", "Minutes", r"minutes?\b|playing time|\bmpg\b", "minutes"),
    _counting("points", "Points", r"points?\b|\bppg\b|\bpts\b|scor\w+|buckets?", "points"),
    Metric("games", "Games played", r"games? (?:played|did|has|have)|(?:how many|most|number of) games?|appearances|missed", total("gp"), 0, unit="games"),
    _season("height", "Height", r"tall\w*|height|short(?:est|er)\b", "inches"), _season("weight", "Weight", r"weigh\w*|heav(?:y|ier|iest)|light(?:er|est)\b", digits=0, suffix=" lbs"),
    _season("age", "Age in the season", r"\bage\b|\bold(?:er|est)?\b|young(?:er|est)\b", digits=0), _season("experience", "Seasons in the league", r"experience\w*|seasons? in the (?:league|nba)|years in the (?:league|nba)|rookie season", digits=0),
]


def own_poss(a):
    return a.fga + 0.44 * a.fta - a.oreb + a.tov


def opp_poss(a):
    return a.a_fga + 0.44 * a.a_fta - a.a_oreb + a.a_tov


ALLOWED = r"(?:allow\w*|conced\w*|g[ai]ves? up|given up|opponents?'?|opposing|against)"


def _team(key, label, words, value, **more):
    return Metric(key, label, words, value, **more)


TEAM_METRICS = [
    _team("close", "Winning % in games decided by 5 points or fewer", r"close games?|clutch games?|tight games?", lambda a: 100 * a.close_wins / a.close_games, suffix="%"),
    _team("opp_three_pct", "Opponent three-point percentage", rf"{ALLOWED} (?:\w+ ){{0,2}}{THREE} ?(?:percentage|shooting|accuracy|%)|defend\w* (?:the )?{THREE}(?: line)?", lambda a: 100 * a.a_tpm / a.a_tpa, suffix="%", lower=True),
    _team("opp_efg", "Opponent effective FG%", rf"{ALLOWED} (?:\w+ ){{0,2}}(?:effective )?(?:field goal|fg|shooting)(?: percentage| %|%)?|opponent shooting", lambda a: 100 * (a.a_fgm + 0.5 * a.a_tpm) / a.a_fga, suffix="%", lower=True),
    _team("forced_tov", "Turnovers forced %", r"forc\w+ (?:the )?(?:most |fewest |more )?turnovers?|turnovers? forced", lambda a: 100 * a.a_tov / opp_poss(a), suffix="%"),
    _team("opp_oreb", "Opponent offensive rebound %", rf"{ALLOWED} (?:\w+ ){{0,2}}offensive rebound\w*", lambda a: 100 * a.a_oreb / (a.a_oreb + a.dreb), suffix="%", lower=True),
    _team("opp_reb", "Opponent rebounds", rf"{ALLOWED} (?:\w+ ){{0,2}}rebounds?", per_game("a_reb"), lower=True),
    _team("opp_points", "Points allowed", rf"{ALLOWED} (?:\w+ ){{0,3}}points?|points? (?:\w+ ){{0,2}}(?:allowed|conceded|against)", per_game("a_points"), lower=True, total=total("a_points"), unit="points allowed"),
    _team("def_rating", "Defensive rating", r"defen[cs]ive rating|drtg|defen[cs]\w*|defend\w*", lambda a: 100 * a.a_points / opp_poss(a), lower=True),
    _team("net_rating", "Net rating", r"net[- ]?(?:rating|rtg)", lambda a: 100 * a.points / own_poss(a) - 100 * a.a_points / opp_poss(a), signed=True),
    _team("off_rating", "Offensive rating", r"offen[cs]ive rating|ortg|offen[cs]es?\b|offensive(?:ly)? (?:teams?|efficien\w*)|efficien\w*", lambda a: 100 * a.points / own_poss(a)),
    _team("pace", "Pace", r"\bpace\b|fast\w*|slow\w*|tempo|possessions", lambda a: 48 * (own_poss(a) + opp_poss(a)) / 2 / (a.minutes / 5)),
    _team("margin", "Point difference per game", r"point (?:difference|differential)|average margin|\bmov\b", per_game("margin"), signed=True, total=total("margin")),
    _team("ts", "True shooting", r"true[- ]?shooting(?: percentage| %)?", lambda a: 100 * a.points / (2 * (a.fga + 0.44 * a.fta)), suffix="%"),
    _team("efg", "Effective FG%", r"effective (?:field goal|fg|shooting)(?: percentage| %)?|\befg%?", lambda a: 100 * (a.fgm + 0.5 * a.tpm) / a.fga, suffix="%"),
    _team("tov_pct", "Turnover %", r"turnover (?:rate|percentage|%)", lambda a: 100 * a.tov / own_poss(a), suffix="%", lower=True),
    _team("oreb_pct", "Offensive rebound %", r"offensive rebound\w* (?:rate|percentage|%)", lambda a: 100 * a.oreb / (a.oreb + a.a_dreb), suffix="%"),
    _team("three_rate", "Share of shots from three", rf"share of shots from {THREE}|{THREE} (?:rate|reliance)|rel(?:y|ies) on {THREE}", lambda a: 100 * a.tpa / a.fga, suffix="%"),
    _team("ft_rate", "Free throw rate", r"free[- ]?throw rate", lambda a: 100 * a.ftm / a.fga, suffix="%"),
    _team("three_pct", "Three-point percentage", rf"{THREE} (?:percentage|accuracy|shooting|shooters?|%)|(?:shoot\w*|accura\w+|percent\w*)[\w \-]{{0,25}}(?:from|on|behind) (?:{THREE}|deep|the arc)|(?:from|on) (?:{THREE}|deep)", lambda a: 100 * a.tpm / a.tpa, suffix="%"),
    _team("tpa", "Threes attempted", rf"{TRIED}[\w \-]{{0,12}} {THREE}|{THREE} {TRIED}", per_game("tpa"), total=total("tpa"), unit="threes attempted"),
    _team("tpm", "Threes made", rf"{THREE}", per_game("tpm"), total=total("tpm"), unit="threes"),
    _team("ft_pct", "Free throw percentage", r"free[- ]?throw (?:percentage|accuracy|shooting|%)|from the (?:free throw |foul )?line", lambda a: 100 * a.ftm / a.fta, suffix="%"),
    _team("fta", "Free throws attempted", rf"free[- ]?throws? {TRIED}|{TRIED}[\w \-]{{0,12}} free[- ]?throws?", per_game("fta"), total=total("fta")),
    _team("ftm", "Free throws made", r"free[- ]?throws?", per_game("ftm"), total=total("ftm")),
    _team("fg_pct", "Field goal percentage", r"field[- ]?goal (?:percentage|accuracy|%)|\bfg%|shooting percentage|from the (?:field|floor)", lambda a: 100 * a.fgm / a.fga, suffix="%"),
    _team("oreb", "Offensive rebounds", r"offensive (?:rebound\w*|boards?)", per_game("oreb"), total=total("oreb")), _team("dreb", "Defensive rebounds", r"defensive (?:rebound\w*|boards?)", per_game("dreb"), total=total("dreb")),
    _team("rebounds", "Rebounds", r"rebound\w*|\bboards?\b", per_game("reb"), total=total("reb"), unit="rebounds"), _team("assists", "Assists", r"assist\w*|passing|pass(?:es)? the ball|ball movement", per_game("ast"), total=total("ast"), unit="assists"),
    _team("steals", "Steals", r"steals?\b", per_game("stl"), total=total("stl")), _team("blocks", "Blocks", r"blocks?\b", per_game("blk"), total=total("blk")),
    _team("turnovers", "Turnovers", r"turnovers?|turn(?:s|ed)? (?:the ball |it )?over", per_game("tov"), lower=True, total=total("tov"), unit="turnovers"), _team("fouls", "Fouls", r"fouls?\b", per_game("pf"), lower=True, total=total("pf")),
    _team("points", "Points", r"points?\b|\bppg\b|scor\w+", per_game("points"), total=total("points"), unit="points"),
    _team("losses", "Losses", r"los[est]\w*|defeats?", lambda a: a.gp - a.won, digits=0, lower=True), _team("wins", "Wins", r"w[io]n(?:s|ning)?\b|records?|standings?|victor\w+|best teams?|worst teams?", total("won"), digits=0),
]
PLAYER_BY_KEY = {m.key: m for m in PLAYER_METRICS}
TEAM_BY_KEY = {m.key: m for m in TEAM_METRICS}
_PATTERNS = {id(table): [(m, re.compile(m.words, re.I)) for m in table] for table in (PLAYER_METRICS, TEAM_METRICS)}


def find_metrics(question: str, table: list[Metric]) -> list[Metric]:
    """Metrics in the order they are mentioned; a stretch of text counts once, for the most specific."""
    left, found = question, []
    for metric, pattern in _PATTERNS[id(table)]:
        while match := pattern.search(left):
            found.append((match.start(), metric))
            left = left[: match.start()] + "\0" * (match.end() - match.start()) + left[match.end() :]
            if match.start() == match.end():
                break
    found.sort(key=lambda item: item[0])
    return list(dict.fromkeys(m for _, m in found))
