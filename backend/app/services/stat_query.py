"""A question as a small structured query: the contract between a reader and the calculation.

A reader (a language model, or a person editing the chips on the Scout page) fills a StatQuery;
query_executor.py checks it and calculates the answer over the season tables of league_data.
The reader never writes a number, so every number in an answer still comes from the database.

The fields, the statistics and the operations were fixed on 2026-11-26, before the fourth test set
(evaluation/web_questions.py) was collected, so that set's wording could not shape them.

topic
  season      averages, totals and rates over the season or a slice of it ("most rebounds per game")
  single_game single games ranked ("most points in a game"), or a player's or team's best game
  game_count  games that meet conditions, counted ("how many 30-point games")
  other       what the structure cannot say: shot zones and types, defenders and matchups, duos and
              lineups, quarters, streaks, standings, similar players, team needs. The rule reader answers.
operation
  rank        order players, teams or games by the measure and keep `limit`
  value       the measure for the named players or teams
  count       how many players or teams meet the conditions (game_count: how many games)
  average/sum the measure over everyone who meets the conditions
  list        everyone who meets the conditions, ordered by the measure
  compare     the named players or teams side by side
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.services.metrics import PLAYER_BY_KEY, TEAM_BY_KEY

STAT_KEYS = sorted(set(PLAYER_BY_KEY) | set(TEAM_BY_KEY))
REASONS = ["other_season_or_career", "playoffs", "awards_or_draft", "not_a_statistic", "not_recorded", "other"]
TOPICS = ["season", "single_game", "game_count", "other"]
OPERATIONS = ["rank", "value", "count", "average", "sum", "list", "compare"]
BASES = ["per_game", "total", "in_game"]  # in_game: the value in one game, to choose or count games
MEASURE_BASES = ["per_game", "total", "per_36"]
OPS = [">=", ">", "<=", "<", "=="]

Stat = Literal[tuple(STAT_KEYS)]  # type: ignore[valid-type]


class Condition(BaseModel):
    stat: Stat
    basis: Literal["per_game", "total", "in_game"] = "per_game"  # rates, sizes and ages ignore it
    op: Literal[">=", ">", "<=", "<", "=="]
    value: float


class Measure(BaseModel):
    stat: Stat
    basis: Literal["per_game", "total", "per_36"] = "per_game"
    plus: list[Stat] = Field(default_factory=list, max_length=4)  # summed with stat: points + rebounds + assists
    divide_by: Stat | None = None  # a ratio of season totals: blocks / fouls, offensive / all rebounds
    multiply: float = 1.0  # e.g. 300 for "share of points from threes" (3 x threes made / points, in %)


class StatQuery(BaseModel):
    answerable: bool = True
    reason: Literal[tuple(REASONS)] | None = None  # type: ignore[valid-type]
    restated: str = Field(default="", max_length=300)  # the question as the reader understood it, in plain English
    topic: Literal["season", "single_game", "game_count", "other"] = "season"
    entity: Literal["player", "team"] = "player"
    players: list[str] = Field(default_factory=list, max_length=8)
    teams: list[str] = Field(default_factory=list, max_length=6)  # the teams the question is about
    on_teams: list[str] = Field(default_factory=list, max_length=6)  # only players of these teams
    opponents: list[str] = Field(default_factory=list, max_length=6)  # only games against these teams
    positions: list[Literal["Guard", "Forward", "Center"]] = Field(default_factory=list)
    conference: Literal["East", "West"] | None = None
    rookies: bool = False
    home: bool | None = None
    won: bool | None = None
    months: list[int] = Field(default_factory=list, max_length=7)
    last_games: int | None = Field(default=None, ge=1, le=82)
    conditions: list[Condition] = Field(default_factory=list, max_length=8)
    measure: Measure | None = None
    operation: Literal["rank", "value", "count", "average", "sum", "list", "compare"] = "rank"
    order: Literal["highest", "lowest"] = "highest"
    limit: int = Field(default=5, ge=1, le=25)


def json_schema() -> dict:
    """The same structure for a model's structured output: every field required, nothing extra."""
    stat = {"type": "string", "enum": STAT_KEYS}
    nullable = lambda schema: {"anyOf": [schema, {"type": "null"}]}  # noqa: E731
    strings = {"type": "array", "items": {"type": "string"}}

    def obj(properties: dict) -> dict:
        return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}

    condition = obj({"stat": stat, "basis": {"type": "string", "enum": BASES}, "op": {"type": "string", "enum": OPS}, "value": {"type": "number"}})
    measure = obj({
        "stat": stat, "basis": {"type": "string", "enum": MEASURE_BASES}, "plus": {"type": "array", "items": stat},
        "divide_by": nullable(stat), "multiply": {"type": "number"},
    })
    return obj({
        "answerable": {"type": "boolean"},
        "reason": nullable({"type": "string", "enum": REASONS}),
        "restated": {"type": "string"},
        "topic": {"type": "string", "enum": TOPICS},
        "entity": {"type": "string", "enum": ["player", "team"]},
        "players": strings, "teams": strings, "on_teams": strings, "opponents": strings,
        "positions": {"type": "array", "items": {"type": "string", "enum": ["Guard", "Forward", "Center"]}},
        "conference": nullable({"type": "string", "enum": ["East", "West"]}),
        "rookies": {"type": "boolean"},
        "home": nullable({"type": "boolean"}),
        "won": nullable({"type": "boolean"}),
        "months": {"type": "array", "items": {"type": "integer"}},
        "last_games": nullable({"type": "integer"}),
        "conditions": {"type": "array", "items": condition},
        "measure": nullable(measure),
        "operation": {"type": "string", "enum": OPERATIONS},
        "order": {"type": "string", "enum": ["highest", "lowest"]},
        "limit": {"type": "integer"},
    })
