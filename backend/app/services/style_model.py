"""How a player plays, as numbers, and a learned distance between players.

Forty-odd features describe a player: volume, shot selection by area and by type, touch, passing,
rebounding and defense. Not every difference matters equally: some features are stable traits,
others are noise. training/train_similarity.py learns that from data (which features separate
different players more than they separate two halves of the same player's season) and stores a
projection in models/similarity.npz. Distances are measured in the projected space.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_FILE = Path(__file__).resolve().parents[2] / "models" / "similarity.npz"
MIN_GAMES, MIN_MINUTES, MIN_SHOTS = 15, 10, 60

ZONE_GROUPS = {
    "rim": ["rim"], "lane": ["lane-low", "lane-high"], "middle": ["ft", "key"], "baseline": ["base-L", "base-R"], "wing two": ["midw-L", "midw-R"],
    "corner three": ["corner-L", "corner-R"], "wing three": ["wing-L", "wing-R", "slot-L", "slot-R"], "top three": ["top"], "deep three": ["deep"],
}
SHOT_FAMILIES = {
    "dunks": "Dunk", "layups": "Layup|Finger Roll", "floaters": "Floating", "hooks": "Hook", "pull-ups": "Pullup|Pull-Up", "step-backs": "Step Back", "fadeaways": "Fadeaway|Turnaround", "tip-ins and putbacks": "Tip|Putback",
    "cuts": "Cutting|Alley Oop", "drives": "Driving", "fast breaks": "Running", "set jump shots": "^Jump Shot$",
}
# feature -> (group, label). The group is what similarity is explained by.
FEATURES: dict[str, tuple[str, str]] = {
    "mpg": ("Role", "Minutes"), "usage": ("Role", "Plays finished per 36"), "pts36": ("Scoring", "Points per 36"), "fga36": ("Scoring", "Shots per 36"), "fta36": ("Scoring", "Free throws attempted per 36"),
    "ts": ("Touch", "True shooting (adjusted)"), "two_pct": ("Touch", "Two-point % (adjusted)"), "three_pct": ("Touch", "Three-point % (adjusted)"), "ft_pct": ("Touch", "Free throw % (adjusted)"),
    "three_rate": ("Shot selection", "Share of shots from three"), "ft_rate": ("Shot selection", "Free throws per shot"), "distance": ("Shot selection", "Average shot distance"),
    "ast36": ("Playmaking", "Assists per 36"), "ast_share": ("Playmaking", "Assists against own shots"), "tov36": ("Playmaking", "Turnovers per 36"), "tov_rate": ("Playmaking", "Turnovers per play"),
    "oreb36": ("Rebounding", "Offensive rebounds per 36"), "dreb36": ("Rebounding", "Defensive rebounds per 36"), "stl36": ("Defense", "Steals per 36"), "blk36": ("Defense", "Blocks per 36"), "pf36": ("Defense", "Fouls per 36"),
    **{f"zone:{z}": ("Shot selection", f"Shots: {z}") for z in ZONE_GROUPS}, **{f"type:{t}": ("Shot selection", f"Shots: {t}") for t in SHOT_FAMILIES},
}
NAMES = list(FEATURES)
GROUPS = list(dict.fromkeys(g for g, _ in FEATURES.values()))
STYLE = [i for i, n in enumerate(NAMES) if FEATURES[n][0] in ("Shot selection", "Playmaking", "Rebounding", "Defense")]


def features(box: pd.DataFrame, shots: pd.DataFrame) -> pd.DataFrame:
    """box: summed box scores per player with gp; shots: player_id, zone, action, three, tries, feet."""
    b = box
    league = b.sum(numeric_only=True)
    out = pd.DataFrame(index=b.index)
    per36 = 36 / b.minutes.clip(lower=1)
    used = b.fga + 0.44 * b.fta + b.tov
    out["mpg"] = b.minutes / b.gp
    out["usage"] = used * per36
    for name, column in (("pts36", "points"), ("fga36", "fga"), ("fta36", "fta"), ("ast36", "ast"), ("tov36", "tov"), ("oreb36", "oreb"), ("dreb36", "dreb"), ("stl36", "stl"), ("blk36", "blk"), ("pf36", "pf")):
        out[name] = b[column] * per36
    # Percentages are pulled toward the league average, the more so the fewer the attempts.
    two_made, two_tried = b.fgm - b.tpm, b.fga - b.tpa
    out["ts"] = (b.points + 120 * league.points / (league.fga + 0.44 * league.fta)) / (2 * (b.fga + 0.44 * b.fta + 120))
    out["two_pct"] = (two_made + 60 * (league.fgm - league.tpm) / (league.fga - league.tpa)) / (two_tried + 60)
    out["three_pct"] = (b.tpm + 80 * league.tpm / league.tpa) / (b.tpa + 80)
    out["ft_pct"] = (b.ftm + 40 * league.ftm / league.fta) / (b.fta + 40)
    out["three_rate"] = (b.tpa + 5 * league.tpa / league.fga) / (b.fga + 5)
    out["ft_rate"] = np.sqrt((b.fta + 5 * league.fta / league.fga) / (b.fga + 5))
    out["ast_share"] = (b.ast + 2) / (b.ast + used + 8)
    out["tov_rate"] = (b.tov + 2) / (used + 16)
    total = shots.groupby("player_id").tries.sum().reindex(b.index).fillna(0)
    out["distance"] = (shots.groupby("player_id").feet.sum().reindex(b.index).fillna(0) + 20 * shots.feet.sum() / shots.tries.sum()) / (total + 20)

    def shares(mask):
        base = shots.tries[mask].sum() / shots.tries.sum()
        tries = shots[mask].groupby("player_id").tries.sum().reindex(b.index).fillna(0)
        return np.sqrt((tries + 10 * base) / (total + 10))  # the root evens out rare and common shots

    for name, zones in ZONE_GROUPS.items():
        out[f"zone:{name}"] = shares(shots.zone.isin(zones))
    for name, pattern in SHOT_FAMILIES.items():
        out[f"type:{name}"] = shares(shots.action.str.contains(pattern, regex=True))
    return out[NAMES].astype(float)


def qualified(box: pd.DataFrame) -> pd.Series:
    return (box.gp >= MIN_GAMES) & (box.minutes / box.gp >= MIN_MINUTES) & (box.fga >= MIN_SHOTS)


def learn(a: np.ndarray, b: np.ndarray, size: int, shrink: float = 0.35) -> np.ndarray:
    """Projection from two halves of each player's season (rows match).

    within:  how much a player differs from himself; between: how much players differ.
    Directions are kept by their ratio, after scaling so that within-player noise is equal
    everywhere, and weighted by reliability: between / (between + within).
    """
    noise = np.cov((a - b).T / np.sqrt(2))
    noise = (1 - shrink) * noise + shrink * np.diag(np.diag(noise)) + 1e-3 * np.eye(len(noise))
    centre = (a + b) / 2
    spread = np.cov(centre.T)
    values, vectors = np.linalg.eigh(noise)
    whiten = vectors @ np.diag(values ** -0.5) @ vectors.T
    ratio, axes = np.linalg.eigh(whiten @ spread @ whiten)
    best = np.argsort(ratio)[::-1][:size]
    signal = np.clip(ratio[best] - 0.5, 1e-6, None)  # the average of two halves still holds half the noise
    return whiten @ axes[:, best] @ np.diag(np.sqrt(signal / (signal + 1)))


@lru_cache(maxsize=1)
def load_model() -> dict:
    stored = np.load(MODEL_FILE)
    return {k: stored[k] for k in stored.files}


def project(x: np.ndarray, kind: str = "overall") -> np.ndarray:
    model = load_model()
    z = np.clip((x - model["mean"]) / model["spread"], -4, 4)
    return z @ model[kind] if kind == "overall" else z[:, STYLE] @ model[kind]


def similarity(distance, kind: str = "overall"):
    """Between 0 and 1. The scale is set so that the median pair of players gets 0.10."""
    return np.exp(-np.power(distance / float(load_model()[f"{kind}_scale"]), 2))
