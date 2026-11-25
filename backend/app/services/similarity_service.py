"""Similar players with the learned distance, and why they are similar.

The vectors are stored in pgvector (player_style_vectors); the features behind them are kept as
numbers so that a match can be explained by area of the game.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.services import league_data as data
from app.services.cache import cached, rows
from app.services.query_embedding_service import to_literal
from app.services.question_reader import Query, sum_players
from app.services.style_model import FEATURES, GROUPS, NAMES, features, load_model, project, qualified, similarity

KINDS = ("overall", "style")
PERCENT = {"ts", "two_pct", "three_pct", "ft_pct", "three_rate", "ast_share", "tov_rate"}


def compute(db) -> pd.DataFrame:
    """Features of every player this season, with the qualified flag; used to build the index."""
    box = sum_players(db, Query(""))
    out = features(box, data.shots(db))
    out["qualified"] = qualified(box)
    return out


def table(db) -> pd.DataFrame:
    """Stored features and vectors, one row per player."""
    def load():
        found = rows(db, text("select player_id, qualified, features, overall::text as overall, style::text as style, archetype from player_style_vectors where season = (select max(season) from player_style_vectors)"))
        frame = pd.DataFrame([{"player_id": r["player_id"], "qualified": r["qualified"], "archetype": r["archetype"], "x": np.array([r["features"][n] for n in NAMES]), **{k: np.array(r[k].strip("[]").split(","), dtype=float) for k in KINDS}} for r in found])
        return frame.set_index("player_id", drop=False)

    return cached("style_table", load)


def rows_for_index(db) -> list[tuple]:
    frame = compute(db)
    x = frame[NAMES].to_numpy()
    vectors = {k: project(x, k) for k in KINDS}
    labels = archetypes(vectors["overall"], x)
    return [
        (int(i), bool(frame.qualified.iloc[n]), {name: round(float(v), 6) for name, v in zip(NAMES, x[n])}, to_literal(vectors["overall"][n]), to_literal(vectors["style"][n]), labels[n] if frame.qualified.iloc[n] else None)
        for n, i in enumerate(frame.index)
    ]


def archetypes(vectors: np.ndarray, x: np.ndarray) -> list[str]:
    model = load_model()
    centres = model["centres"]
    nearest = ((vectors[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    return [str(model["centre_names"][i]) for i in nearest]


def neighbours(db, player_id: int, kind: str = "overall", limit: int = 10, min_age=None, max_age=None, position=None, is_active=None, team_id=None) -> list[dict]:
    """Nearest players; the filters and the vector distance are one pgvector query."""
    if kind not in KINDS:
        raise ValueError("unknown kind of similarity")
    conditions = ["v.season = me.season", "v.player_id <> me.player_id", "v.qualified"]
    params = {"me": player_id, "limit": limit}
    for value, name, condition in (
        (min_age, "min_age", "(d.meta->>'age')::float >= :min_age"), (max_age, "max_age", "(d.meta->>'age')::float <= :max_age"), (team_id, "team_id", "d.team_ids @> array[cast(:team_id as int)]"),
        (position.strip().lower() if position and position.strip() else None, "position", "strpos(lower(d.meta->>'position'), :position) > 0"),
        (is_active, "is_active", "exists (select 1 from players p where p.id = v.player_id and p.is_active = :is_active)"),
    ):
        if value is not None:
            conditions.append(condition)
            params[name] = value
    db.execute(text("set local hnsw.iterative_scan = strict_order"))
    db.execute(text("set local hnsw.ef_search = 100"))
    found = rows(db, text(f"""
        select v.player_id, v.archetype, v.{kind} <-> me.{kind} as distance, d.content, d.title, d.entity, d.kind, d.season, d.player_ids, d.team_ids
        from (select * from player_style_vectors where player_id = :me order by season desc limit 1) me
        join player_style_vectors v on true
        join rag_documents d on d.kind = 'player_season' and d.entity = 'player:' || v.player_id and d.season = v.season
        where {' and '.join(conditions)} order by v.{kind} <-> me.{kind} limit :limit
    """), params)
    for r in found:
        r["similarity"] = float(similarity(r["distance"], kind))
    return found


def shown(name: str, value: float) -> tuple[float, bool]:
    """The value as people know it: shares were stored as square roots."""
    if name.startswith(("zone:", "type:")):
        return value**2 * 100, True
    if name == "ft_rate":
        return value**2, False
    return (value * 100, True) if name in PERCENT else (value, False)


def explain(db, a: int, b: int) -> dict:
    """Closeness by area of the game, and the features that bring two players together or apart."""
    frame, model = table(db), load_model()
    if a not in frame.index or b not in frame.index:
        return {"areas": [], "alike": [], "apart": []}
    xa, xb = frame.at[a, "x"], frame.at[b, "x"]
    za, zb = (np.clip((x - model["mean"]) / model["spread"], -4, 4) for x in (xa, xb))
    items = []
    for i, name in enumerate(NAMES):
        group, label = FEATURES[name]
        own, percent = shown(name, xa[i])
        other, _ = shown(name, xb[i])
        gap = abs(float(za[i] - zb[i]))
        together = min(abs(za[i]), abs(zb[i])) if za[i] * zb[i] > 0 else 0
        items.append({"name": name, "group": group, "label": label, "percent": percent, "own": own, "other": other, "gap": gap, "shared": float(together) - gap, "closeness": max(0.0, 1 - gap / 2), "high": bool(za[i] > 0.3 and zb[i] > 0.3)})
    areas = [{"label": g, "closeness": float(np.exp(-np.mean([i["gap"] ** 2 for i in items if i["group"] == g]) / 2))} for g in GROUPS]
    # Distinctive numbers both players share come first; matching on an average number says little.
    alike = sorted(items, key=lambda d: -d["shared"])[:6]
    apart = [d for d in sorted(items, key=lambda d: -d["gap"]) if d["gap"] >= 0.6 and d not in alike][:4]

    def slim(d):
        return {k: d[k] for k in ("label", "percent", "own", "other", "closeness", "high")}

    return {"areas": areas, "alike": [slim(d) for d in alike], "apart": [slim(d) for d in apart]}


def matrix(db, kind: str = "overall") -> tuple[list[int], np.ndarray]:
    """Vectors of all qualified players, for scoring many candidates at once."""
    frame = table(db)
    frame = frame[frame.qualified]
    return list(frame.player_id), np.vstack(frame[kind].to_list())
