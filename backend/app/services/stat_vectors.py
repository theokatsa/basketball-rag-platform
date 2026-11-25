"""Statistical player vectors.

Every player-season becomes a vector of z-scores computed within its own season, so
players are compared by how they played rather than by how their profile is worded.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from sqlalchemy import text

FEATURES = [
    "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers",
    "field_goal_pct", "three_point_attempts", "three_point_shrunk",
    "free_throw_attempts", "free_throw_shrunk",
]

# Percentages on few attempts are pulled toward the league average.
THREE_POINT_PRIOR = 50
FREE_THROW_PRIOR = 30
# Players below these limits are too noisy to define the scale or to be suggested.
MIN_GAMES = 10
MIN_MINUTES = 8
CACHE_SECONDS = 600

TRAITS = {
    "points": "high-volume scorer",
    "rebounds": "strong rebounder",
    "assists": "primary playmaker",
    "steals": "disruptive perimeter defender",
    "blocks": "rim protector",
    "field_goal_pct": "efficient finisher",
    "three_point_attempts": "high-volume three-point shooter",
    "three_point_shrunk": "accurate three-point shooter",
    "free_throw_attempts": "draws many fouls",
    "free_throw_shrunk": "reliable free throw shooter",
}

_SQL = text(
    """
    with attempts as (
        select player_id, season,
               avg(tpa) as three_point_attempts,
               avg(fta) as free_throw_attempts,
               sum(tpm) as tpm, sum(tpa) as tpa, sum(ftm) as ftm, sum(fta) as fta
        from player_box_scores
        group by player_id, season
    )
    select s.player_id, p.full_name, p.is_active, s.season, s.games_played,
           pp.age, pp.position, t.full_name as team_name,
           s.minutes, s.points, s.rebounds, s.assists, s.steals, s.blocks, s.turnovers,
           s.field_goal_pct, s.three_point_pct, s.free_throw_pct,
           a.three_point_attempts, a.free_throw_attempts, a.tpm, a.tpa, a.ftm, a.fta
    from player_season_stats s
    join players p on p.id = s.player_id
    left join player_profiles pp on pp.player_id = s.player_id
    left join teams t on t.id = s.team_id
    left join attempts a on a.player_id = s.player_id and a.season = s.season
    where s.season = :season
    """
)


@dataclass
class SeasonVectors:
    season: str
    rows: list[dict]
    z: np.ndarray  # clipped, for distances
    raw: np.ndarray  # unclipped, for rankings
    index: dict[int, int]

    def traits(self, player_id: int) -> list[str]:
        i = self.index[player_id]
        if not _qualifies(self.rows[i]):
            return []
        ranked = sorted(
            ((self.z[i][j], name) for j, name in enumerate(FEATURES) if name in TRAITS),
            reverse=True,
        )
        return [TRAITS[name] for value, name in ranked if value >= 1.0][:4]

    def shared_traits(self, a: int, b: int) -> list[str]:
        other = set(self.traits(b))
        return [trait for trait in self.traits(a) if trait in other]

    def leaders(self, features: list[str]) -> list[tuple[dict, float]]:
        """Qualified players by their weakest of the asked skills blended with the mean.

        The score is the share of qualified players they beat (0-1).
        """
        block = self.raw[:, [FEATURES.index(name) for name in features]]
        score = 0.5 * block.mean(axis=1) + 0.5 * block.min(axis=1)
        order = [i for i in np.argsort(-score, kind="stable") if _qualifies(self.rows[i])]
        return [(self.rows[i], 1 - rank / len(order)) for rank, i in enumerate(order)]

    def neighbours(self, player_id: int) -> list[tuple[dict, float]]:
        """Qualified players, closest first, with a 0-1 similarity."""
        i = self.index[player_id]
        distance = np.sqrt(np.mean((self.z - self.z[i]) ** 2, axis=1))
        order = np.argsort(distance, kind="stable")
        return [
            (self.rows[j], math.exp(-float(distance[j]) ** 2 / 2))
            for j in order
            if j != i and _qualifies(self.rows[j])
        ]


def _qualifies(row: dict) -> bool:
    return (row["games_played"] or 0) >= MIN_GAMES and (row["minutes"] or 0) >= MIN_MINUTES


_cache: dict[str, tuple[float, SeasonVectors]] = {}


def latest_season(connection) -> str | None:
    return connection.execute(text("select max(season) from player_season_stats")).scalar()


def load_season(connection, season: str | None = None) -> SeasonVectors | None:
    season = season or latest_season(connection)
    if season is None:
        return None
    cached = _cache.get(season)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    rows = [dict(row) for row in connection.execute(_SQL, {"season": season}).mappings()]
    if not rows:
        return None

    def total(key):
        return float(sum(row[key] or 0 for row in rows))

    league_three = total("tpm") / max(total("tpa"), 1)
    league_free = total("ftm") / max(total("fta"), 1)
    for row in rows:
        row["three_point_shrunk"] = (float(row["tpm"] or 0) + THREE_POINT_PRIOR * league_three) / (float(row["tpa"] or 0) + THREE_POINT_PRIOR)
        row["free_throw_shrunk"] = (float(row["ftm"] or 0) + FREE_THROW_PRIOR * league_free) / (float(row["fta"] or 0) + FREE_THROW_PRIOR)

    matrix = np.array([[float(row[name] or 0) for name in FEATURES] for row in rows])
    pool = np.array([_qualifies(row) for row in rows])
    reference = matrix[pool] if pool.sum() >= 2 else matrix
    spread = reference.std(axis=0)
    raw = (matrix - reference.mean(axis=0)) / np.where(spread == 0, 1, spread)
    vectors = SeasonVectors(season, rows, np.clip(raw, -3.5, 3.5), raw, {row["player_id"]: i for i, row in enumerate(rows)})
    _cache[season] = (time.monotonic(), vectors)
    return vectors


def describe(vectors: SeasonVectors, player_id: int) -> str:
    """Evidence text for one player-season; also what the text embedding is built from."""
    row = vectors.rows[vectors.index[player_id]]
    role = (row["position"] or "player").lower().strip()
    team = f" for the {row['team_name']}" if row["team_name"] else ""

    def pct(key):
        return f"{(row[key] or 0) * 100:.1f}%"

    sentences = [
        f"{row['full_name']} is a {role} who played {row['games_played']} games{team} in {row['season']}.",
        f"Averages: {row['minutes']:.1f} minutes, {row['points']:.1f} points, {row['rebounds']:.1f} rebounds, "
        f"{row['assists']:.1f} assists, {row['steals']:.1f} steals, {row['blocks']:.1f} blocks and {row['turnovers']:.1f} turnovers.",
        f"Shooting: {pct('field_goal_pct')} from the field, {pct('three_point_pct')} from three on "
        f"{float(row['three_point_attempts'] or 0):.1f} attempts, {pct('free_throw_pct')} on free throws.",
    ]
    traits = vectors.traits(player_id)
    if traits:
        sentences.append(f"Strengths: {', '.join(traits)}.")
    if row["age"] is not None:
        sentences.append(f"Current age on record: {row['age']}.")
    return " ".join(sentences)
