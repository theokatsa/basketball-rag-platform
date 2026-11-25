"""Teams that play alike: pace, shot selection and how they win possessions, not how good they are."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services import league_data as data
from app.services.cache import cached
from app.services.style_model import ZONE_GROUPS

LABELS = {
    "pace": "Pace", "three_rate": "Share of shots from three", "ft_rate": "Free throws per shot", "assist_rate": "Baskets assisted", "oreb": "Offensive rebounding", "tov": "Turnover rate", "stl": "Steals", "blk": "Blocks",
    "opp_three_rate": "Threes allowed", "opp_ft_rate": "Free throws allowed", "opp_tov": "Turnovers forced", "opp_oreb": "Offensive rebounds allowed", **{f"zone:{z}": f"Shots: {z}" for z in ZONE_GROUPS},
}


def team_features(games: pd.DataFrame, shots: pd.DataFrame) -> pd.DataFrame:
    """games: team rows with the opponent's a_*; shots: team, zone, tries."""
    s = games.groupby("team").sum(numeric_only=True)
    poss, opp = s.fga + 0.44 * s.fta - s.oreb + s.tov, s.a_fga + 0.44 * s.a_fta - s.a_oreb + s.a_tov
    out = pd.DataFrame({
        "pace": 48 * (poss + opp) / 2 / (s.minutes / 5), "three_rate": s.tpa / s.fga, "ft_rate": s.fta / s.fga, "assist_rate": s.ast / s.fgm, "oreb": s.oreb / (s.oreb + s.a_dreb), "tov": s.tov / poss, "stl": s.stl / opp, "blk": s.blk / opp,
        "opp_three_rate": s.a_tpa / s.a_fga, "opp_ft_rate": s.a_fta / s.a_fga, "opp_tov": s.a_tov / opp, "opp_oreb": s.a_oreb / (s.a_oreb + s.dreb),
    })
    total = shots.groupby("team").tries.sum()
    for name, zones in ZONE_GROUPS.items():
        out[f"zone:{name}"] = shots[shots.zone.isin(zones)].groupby("team").tries.sum() / total
    return out[list(LABELS)]


def standardise(x: pd.DataFrame) -> pd.DataFrame:
    return (x - x.mean()) / x.std()


def _table(db) -> pd.DataFrame:
    return cached("team_style", lambda: standardise(team_features(data.team_games(db), data.shots(db))))


def similar_teams(db, team_id: int, limit: int = 5) -> list[dict] | None:
    z = _table(db)
    if team_id not in z.index:
        return None
    d = np.sqrt(((z - z.loc[team_id]) ** 2).mean(axis=1))
    pairs = np.sqrt(((z.to_numpy()[:, None, :] - z.to_numpy()[None, :, :]) ** 2).mean(axis=2))
    scale = np.median(pairs[np.triu_indices(len(z), 1)]) / np.sqrt(np.log(4))  # a typical pair of teams gets 25%
    out = []
    for other in d.drop(team_id).sort_values().index[:limit]:
        shared = [(min(abs(z.at[team_id, f]), abs(z.at[other, f])), f) for f in z if z.at[team_id, f] * z.at[other, f] > 0 and abs(z.at[team_id, f] - z.at[other, f]) < 1]
        traits = [f"{'high' if z.at[team_id, f] > 0 else 'low'} {LABELS[f].lower().replace('shots: ', 'share of shots: ')}" for v, f in sorted(shared, reverse=True)[:3] if v > 0.4]
        out.append({"team_id": int(other), "similarity": float(np.exp(-((d[other] / scale) ** 2))), "shared": traits})
    return out
