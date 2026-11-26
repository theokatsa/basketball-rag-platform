"""A language model reads the question into a StatQuery (stat_query.py); it never writes a number.

The model gets the contract, the list of statistics and ten examples written for this prompt (none
from a test set), and must answer with JSON that fits the schema (structured output). A result that
does not validate is retried once with the error, then given up: the rule reader answers instead.

READER_MODEL chooses the model (default: OPENROUTER_MODEL). With READER_CACHE set to a file, answers
are kept there by model, prompt version and question, so an evaluation can be repeated exactly.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.core.config import LLM_TIMEOUT_SECONDS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL
from app.services.metrics import PLAYER_METRICS, TEAM_METRICS
from app.services.stat_query import StatQuery, json_schema

log = logging.getLogger(__name__)
PROMPT_VERSION = "reader-1"
READER_MODEL = os.getenv("READER_MODEL", "").strip() or OPENROUTER_MODEL
CACHE = os.getenv("READER_CACHE", "").strip()

RULES = """You read questions about NBA statistics and turn each into a JSON query for a database. You never answer the question and never write a statistic yourself: the database calculates everything.

The database holds the 2024-25 NBA regular season only: every player's and team's box score in every game (minutes, points, field goals, three-pointers, free throws, offensive and defensive rebounds, assists, steals, blocks, turnovers, fouls, plus-minus, the opponent and the date); each player's team, position, height, weight, age and years in the league; season advanced statistics (usage, offensive, defensive and net rating, assist, rebound and turnover rates, PIE, how opponents shoot when he guards them).

Set answerable to false, with a reason, when the database cannot answer:
- other_season_or_career: any other season, careers, all-time or franchise records, "ever", "in history", "last season", current or live games, comparing seasons.
- playoffs: playoffs, the Finals, conference finals, the play-in, the NBA Cup final.
- awards_or_draft: MVP and other awards, All-Star or All-NBA, the draft, contracts, salaries, trades.
- not_a_statistic: opinions, character, health and injuries, predictions, anything you would have to watch a game or ask someone to know.
- not_recorded: statistics that are not kept: fast-break points, second-chance points, points in the paint, points off turnovers, lead changes, times tied, largest lead, team rebounds, and-ones, PER, box plus-minus, win shares, betting lines, fantasy points, moments inside a game, a player's points by quarter.
- other: anything else outside these data.
A question that names no season, or says "this season", means 2024-25. A year alone names the season that ends in it: "2025" is 2024-25, "2024" is 2023-24.

topic:
- season: averages, totals and rates over the season or over some of its games.
- single_game: single games ranked, or a player's or team's best game ("most points in a game", "season high").
- game_count: games that meet conditions, counted ("how many 30-point games", "most games with 10 assists").
- other: the database can answer, but not with these fields: shot zones and shot types (corner threes, dunks, mid-range), who guards whom and one-on-one matchups, duos, pairs and lineups, team scoring by quarter, streaks, standings, seeds and head-to-head series, similar players, what a team needs, a player's strengths or style in words.

Fields:
- entity: "player" or "team".
- players, teams: who the question asks about by name, written in full ("LeBron James", "Boston Celtics"). Empty for questions about the whole league.
- on_teams: only players of these teams. opponents: only games against these teams.
- positions (Guard, Forward, Center), rookies (in their first season), conference (East or West): who counts.
- home (true at home, false on the road), won (true in wins, false in losses), months (1-12), last_games: which games count. Leave null or empty when the question does not say.
- conditions: filters, each {stat, basis, op, value}. basis per_game is a season average, total a season total, in_game the value in one game (for single_game and game_count). Games played: stat games, basis total. Heights in inches (6'8" is 80, 7 feet is 84). Percentages as numbers: 40 for 40%. Add a minimum only when the question states one; the database applies the usual qualifying minimums itself.
- measure: the number to rank, report, compare or average: {stat, basis, plus, divide_by, multiply}. basis per_game, total or per_36 (rates ignore it). plus: statistics added to stat ("points, rebounds and assists combined"). divide_by: a ratio of season totals ("blocks per foul": stat blocks, divide_by fouls). multiply: 1, or 100 to show a share as a percentage. null only when counting without ranking.
- For counting statistics, "per game", "average", "a game", "leader", "top scorer" mean per_game; "total", "in all", or "most X this season" without "per game" mean total.
- operation: rank (best or worst, as many as limit), value (for the named players or teams), compare (named ones side by side), count (how many), average or sum (over everyone who meets the conditions), list (everyone who meets the conditions).
- order: highest or lowest. "Fewest", "worst shooting" are lowest. For defensive rating, points allowed and turnovers, "best" is lowest.
- limit: 1 for "who has the most", else the number asked for, else 5.
- restated: the question as one plain sentence, as you understood it, with names in full.

Statistics for players: {players}
Statistics for teams: {teams}
Answer with the JSON object only."""


def _catalog(metrics) -> str:
    return "; ".join(f"{m.key} ({m.label})" for m in metrics)


def _example(**fields) -> str:
    return StatQuery.model_validate(fields).model_dump_json()


def _m(stat, basis="per_game", **more) -> dict:
    return {"stat": stat, "basis": basis, "plus": more.get("plus", []), "divide_by": more.get("divide_by"), "multiply": more.get("multiply", 1)}


EXAMPLES = [
    ("Who averaged the most rebounds among guards?", _example(restated="Which guard averaged the most rebounds per game?", positions=["Guard"], measure=_m("rebounds"), operation="rank", limit=1)),
    ("How many 40-point games did Luka Doncic have at home?", _example(restated="How many home games did Luka Dončić score at least 40 points in?", topic="game_count", players=["Luka Doncic"], home=True,
                                                                         conditions=[{"stat": "points", "basis": "in_game", "op": ">=", "value": 40}], operation="value")),
    ("best three point shooters with at least 300 attempts", _example(restated="Who had the best three-point percentage with at least 300 attempts?",
                                                                      conditions=[{"stat": "tpa", "basis": "total", "op": ">=", "value": 300}], measure=_m("three_pct"), operation="rank", limit=5)),
    ("Which team allowed the fewest points per game?", _example(restated="Which team allowed the fewest points per game?", entity="team", measure=_m("opp_points"), operation="rank", order="lowest", limit=1)),
    ("What was Nikola Jokic's career high in assists?", _example(answerable=False, reason="other_season_or_career", restated="Nikola Jokić's career high in assists.", players=["Nikola Jokic"], topic="single_game", measure=_m("assists"), operation="value")),
    ("Who guards Stephen Curry best?", _example(restated="Which defender held Stephen Curry best in their matchups?", topic="other", players=["Stephen Curry"], operation="rank", limit=1)),
    ("Average age of the players who scored 25 a game", _example(restated="The average age of players who averaged at least 25 points per game.",
                                                                 conditions=[{"stat": "points", "basis": "per_game", "op": ">=", "value": 25}], measure=_m("age"), operation="average")),
    ("Most points in a game by a rookie", _example(restated="The most points a rookie scored in one game.", topic="single_game", rookies=True, measure=_m("points"), operation="rank", limit=1)),
    ("Celtics record on the road", _example(restated="The Boston Celtics' win-loss record in away games.", entity="team", teams=["Boston Celtics"], home=False, measure=_m("wins"), operation="value")),
    ("Is Ja Morant a good leader?", _example(answerable=False, reason="not_a_statistic", restated="Whether Ja Morant is a good leader.", players=["Ja Morant"], operation="value")),
]


def system_prompt() -> str:
    return RULES.replace("{players}", _catalog(PLAYER_METRICS)).replace("{teams}", _catalog(TEAM_METRICS))


@dataclass
class Reading:
    query: StatQuery | None
    model: str = READER_MODEL
    ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str = ""
    raw: list[str] = field(default_factory=list)


_memory: dict[str, Reading] = {}


def _key(question: str, previous: str | None, history: list[str] | None = None) -> str:
    parts = [READER_MODEL, PROMPT_VERSION, question.strip(), (previous or "").strip()]
    return json.dumps(parts + ([h.strip() for h in history] if history else []), ensure_ascii=False)  # without history: the key of before


def _load_cache() -> dict[str, dict]:
    if not CACHE or not Path(CACHE).exists():
        return {}
    out = {}
    for line in Path(CACHE).read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            out[item["key"]] = item
    return out


_disk = _load_cache()


def _messages(question: str, previous: str | None, retry: str | None, history: list[str] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt()}]
    for asked, answer in EXAMPLES:
        messages += [{"role": "user", "content": f"Question: {asked}"}, {"role": "assistant", "content": answer}]
    if history:  # a conversation: resolve "he", "and at home?" and "what about Jokic?" from the earlier questions
        earlier = "; ".join(f"{n}. {h}" for n, h in enumerate(history, 1))
        text = f"Question: {question}\n(Earlier questions in this conversation, oldest first: {earlier})"
    else:
        text = f"Question: {question}" + (f"\n(The question before it was: {previous})" if previous else "")
    messages.append({"role": "user", "content": text})
    if retry:
        messages += [{"role": "assistant", "content": retry.split("\n", 1)[1] if "\n" in retry else "{}"},
                     {"role": "user", "content": f"That was not valid: {retry.split(chr(10), 1)[0]}. Answer again with the JSON object only."}]
    return messages


def _call(messages: list[dict]) -> tuple[str, dict]:
    response = httpx.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "http://localhost:5173", "X-Title": "NBAmeetsdata"},
        json={
            "model": READER_MODEL, "messages": messages, "temperature": 0, "max_tokens": 900,
            "response_format": {"type": "json_schema", "json_schema": {"name": "stat_query", "strict": True, "schema": json_schema()}},
            "provider": {"require_parameters": True},
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:  # the provider's message (it can name the key's settings page) stays in the log
        log.warning("reader request failed: %s %s", response.status_code, response.text[:300])
        raise RuntimeError(f"HTTP {response.status_code}")
    data = response.json()
    return data["choices"][0]["message"]["content"] or "", data.get("usage") or {}


def read(question: str, previous: str | None = None, history: list[str] | None = None) -> Reading:
    """The question as a StatQuery, or a Reading with query None and the reason in error."""
    if not OPENROUTER_API_KEY:
        return Reading(None, error="no key")
    key = _key(question, previous, history)
    if key in _memory:
        return _memory[key]
    if key in _disk:
        item = _disk[key]
        reading = Reading(StatQuery.model_validate(item["query"]) if item["query"] else None, item["model"], item["ms"], item["prompt_tokens"], item["completion_tokens"], item["error"], item["raw"])
        _memory[key] = reading
        return reading
    started, reading, retry = time.perf_counter(), Reading(None), None
    for _ in range(2):
        try:
            content, usage = _call(_messages(question, previous, retry, history))
        except Exception as error:  # noqa: BLE001 - network, credit, timeout: the rule reader answers
            reading.error = f"{type(error).__name__}: {str(error)[:160]}"
            break
        reading.raw.append(content)
        reading.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        reading.completion_tokens += int(usage.get("completion_tokens") or 0)
        try:
            text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            reading.query, reading.error = StatQuery.model_validate(json.loads(text)), ""
            break
        except (json.JSONDecodeError, ValidationError) as error:
            reading.error = f"invalid: {str(error).splitlines()[0][:160]}"
            retry = f"{reading.error}\n{content[:2000]}"
    reading.ms = round((time.perf_counter() - started) * 1000)
    if reading.query is not None or reading.error.startswith("invalid"):  # not network, credit or rate-limit failures
        _memory[key] = reading
        if CACHE:
            item = {"key": key, "query": reading.query.model_dump() if reading.query else None, "model": reading.model, "ms": reading.ms,
                    "prompt_tokens": reading.prompt_tokens, "completion_tokens": reading.completion_tokens, "error": reading.error, "raw": reading.raw}
            with open(CACHE, "a", encoding="utf-8") as out:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")
            _disk[key] = item
    return reading
