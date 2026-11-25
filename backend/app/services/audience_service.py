"""What people look at: most viewed, trending, overlooked, and who is viewed together.

Counts are of different users, not of page openings, so one person reloading a page counts once.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.services import league_data as data
from app.services.cache import rows

FRESH_SECONDS = 120  # a view shows up in the rankings within two minutes
TREND_DAYS, BASE_DAYS = 5, 28
GEM_MIN_SCORE = 65
MIN_TOGETHER = 2  # users
MIN_SURPRISE = 3.0  # with hundreds of players, smaller surprises happen by chance
_kept: dict = {}


def _recent(key, load):
    hit = _kept.get(key)
    if hit and time.monotonic() - hit[0] < FRESH_SECONDS:
        return hit[1]
    value = load()
    _kept[key] = (time.monotonic(), value)
    return value


def info(db) -> dict:
    """How much of the audience is simulated, so that pages can say so."""
    return _recent("info", lambda: rows(db, text("select count(*) as users, count(*) filter (where is_simulated) as simulated from app_users"))[0])


def viewers(db, newest: int | None = None, oldest: int = 0) -> pd.Series:
    """Different users per player, between `newest` and `oldest` days ago (newest None: ever)."""
    def load():
        since = "" if newest is None else "and viewed_at > now() - make_interval(days => :a)"
        until = "and viewed_at <= now() - make_interval(days => :b)" if oldest else ""
        found = rows(db, text(f"select player_id, count(distinct user_id) as n from player_views where true {since} {until} group by 1"), {k: v for k, v in (("a", newest), ("b", oldest)) if f":{k}" in since + until})
        return pd.Series({r["player_id"]: r["n"] for r in found}, dtype=float)

    return _recent(("viewers", newest, oldest), load)


def _allowed(db, position: str | None) -> pd.DataFrame:
    folk = data.people(db)
    return folk[folk.position.str.contains(position)] if position else folk


def most_viewed(db, days: int | None = None, position: str | None = None, limit: int = 10) -> list[dict]:
    """days None: ever. previous is the place in the period of the same length before."""
    now = viewers(db, days)
    before = viewers(db, days * 2, days) if days else pd.Series(dtype=float)
    folk = _allowed(db, position)
    now, before = now[now.index.isin(folk.index)], before[before.index.isin(folk.index)]
    order = now.sort_values(ascending=False, kind="stable")
    earlier = {p: n for n, p in enumerate(before.sort_values(ascending=False, kind="stable").index, 1)}
    return [{"player_id": int(p), "viewers": int(n), "previous": earlier.get(p), "detail": None} for p, n in order.head(limit).items()]


def trending(db, position: str | None = None, limit: int = 10) -> list[dict]:
    """Players viewed more in the last days than their usual share of the traffic explains.

    expected = traffic of the last days x the player's share of the weeks before (plus half a view,
    so that a newcomer is possible). The surprise is measured in standard deviations of a count.
    """
    def load():
        return rows(db, text(f"""
            select player_id, count(*) filter (where viewed_at > now() - interval '{TREND_DAYS} days') as recent,
                   count(*) filter (where viewed_at <= now() - interval '{TREND_DAYS} days') as earlier
            from (select distinct on (user_id, player_id, viewed_at::date) user_id, player_id, viewed_at from player_views
                  where viewed_at > now() - interval '{TREND_DAYS + BASE_DAYS} days') v group by 1"""))

    frame = pd.DataFrame(_recent("trend", load), columns=["player_id", "recent", "earlier"]).set_index("player_id")
    if not len(frame) or not frame.recent.sum():
        return []
    share = (frame.earlier + 0.5) / (frame.earlier.sum() + 0.5 * len(frame))
    frame["expected"] = share * frame.recent.sum()
    frame["surprise"] = (frame.recent - frame.expected) / np.sqrt(frame.expected + 1)
    frame = frame[frame.index.isin(_allowed(db, position).index) & (frame.recent >= 5) & (frame.surprise >= MIN_SURPRISE)]
    return [
        {"player_id": int(p), "viewers": int(r.recent), "previous": None, "detail": f"{r.recent:.0f} views in {TREND_DAYS} days, {r.expected:.0f} expected", "surprise": float(r.surprise)}
        for p, r in frame.sort_values("surprise", ascending=False).head(limit).iterrows()
    ]


def hidden_gems(db, position: str | None = None, limit: int = 10) -> list[dict]:
    """Good players few people look at: the gap between the places by overall score and by viewers."""
    seen = viewers(db)
    folk = data.people(db)
    folk = folk[(folk.gp >= 30) & (folk.mpg >= 15)]
    by_score = folk.overall_score.astype(float).rank(pct=True)
    by_views = seen.reindex(folk.index).fillna(0).rank(pct=True)
    gap = (by_score - by_views)[folk.overall_score.astype(float) >= GEM_MIN_SCORE]
    if position:
        gap = gap[[position in p for p in folk.position.reindex(gap.index)]]
    return [
        {"player_id": int(p), "viewers": int(seen.get(p, 0)), "previous": None, "detail": f"Overall score {folk.at[p, 'overall_score']:.0f}, viewed less than {100 * (1 - by_views[p]):.0f}% of players"}
        for p in gap.sort_values(ascending=False).head(limit).index
    ]


def player_audience(db, player_id: int) -> dict:
    seen = viewers(db)
    n = int(seen.get(player_id, 0))
    return {"viewers": n, "rank": int((seen > n).sum()) + 1 if n else None, "players": int(len(seen)), **info(db)}


def also_viewed(db, player_id: int, limit: int = 6) -> list[dict]:
    """Learned lists (training/train_also_viewed.py). Only pairs somebody really opened together:
    the model orders them, it does not invent them. One person is not enough: that would show what
    somebody in particular looked at."""
    return rows(db, text("""
        select other_id as player_id, viewers, audience, score from player_also_viewed
        where player_id = :p and viewers >= :least order by rank limit :n"""), {"p": player_id, "n": limit, "least": MIN_TOGETHER})


def links(db, players: list[int]) -> dict[int, dict[int, float]]:
    """For each player, where his audience goes next (across visits)."""
    out: dict[int, dict[int, float]] = {}
    for r in rows(db, text("select player_id, other_id, weight from player_audience_links where player_id = any(:p)"), {"p": players}):
        out.setdefault(r["player_id"], {})[r["other_id"]] = r["weight"]
    return out
