"""Maps a paraphrased question to a measurable skill by meaning.

"Who is careless with the basketball?" contains no statistic name, so the word rules miss it.
Its embedding is compared with plain descriptions of each skill instead. The vectors choose
which column to rank by, and SQL does the ranking.
"""

from functools import lru_cache

import numpy as np

from app.services.query_embedding_service import encode

CONCEPTS = {
    ("blocks",): ["a player who protects the rim and blocks shots", "prevents opponents from scoring near the basket", "shot blocker in the paint"],
    ("rebounds",): ["a player who grabs many rebounds", "collects missed shots off the backboard", "strong on the boards"],
    ("assists",): ["a playmaker who sets up teammates with passes", "point guard who runs the offense and creates shots for others", "great passer with vision", "floor general"],
    ("steals",): ["a defender who steals the ball and intercepts passes", "forces turnovers with quick hands"],
    ("three_point_attempts", "three_point_shrunk"): ["a long range three-point shooter", "makes shots from beyond the arc", "sniper from deep", "downtown shooter"],
    ("points",): ["a high volume scorer who carries the scoring load", "scores many points every game", "go-to scorer", "bucket getter"],
    ("turnovers",): ["a player who loses the ball often", "careless with the ball, commits many turnovers"],
    ("free_throw_shrunk",): ["a reliable free throw shooter", "makes foul shots"],
}
# Chosen on the development questions: unrelated questions stay below 0.52.
MIN_SIMILARITY = 0.55
# Word rules are trusted unless the meaning very clearly points elsewhere.
OVERRULE_SIMILARITY = 0.75


@lru_cache(maxsize=1)
def _concept_vectors():
    return {skills: encode(phrases) for skills, phrases in CONCEPTS.items()}


def route(question: str) -> tuple[list[str], float]:
    vector = encode([question])[0]
    best, skills = max((float(np.max(matrix @ vector)), skills) for skills, matrix in _concept_vectors().items())
    return list(skills), best
