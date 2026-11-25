"""Suggested players for a person, and players who would help a team.

Suggestions follow what someone looks at, and work without an account because the lists come
with the request. A person can have several interests at once (rim protectors and passing
guards), so candidates are compared with each seed, not with an average of them, and the final
list is spread out so that it is not eight versions of the same player.
"""

from __future__ import annotations

import numpy as np

from app.services import league_data as data
from app.services.audience_service import links
from app.services.insight_service import SKILLS, load_profiles, main_position
from app.services.similarity_service import explain, matrix, table
from app.services.style_model import similarity

WEIGHTS = {"favorites": 3.0, "compared": 2.0, "viewed": 1.0}
RECENCY = 0.9  # each older view counts a little less
VARIETY = 0.35  # how much a candidate loses for resembling one already chosen
PER_SEED = 3
MIN_GAMES = 20
AUDIENCE_SHARE = 0.45  # weight of what people open against how players play; a judgement, see docs
MIN_MATCH = 0.3  # a typical pair of players has 0.1
STAR_WEIGHT = 0.25  # how much general quality counts next to filling the team's gaps


def _seeds(favorites: list[int], compared: list[int], viewed: list[int]) -> dict[int, float]:
    out: dict[int, float] = {}
    for ids, kind in ((favorites, "favorites"), (compared, "compared")):
        for i in ids:
            out[i] = out.get(i, 0) + WEIGHTS[kind]
    for n, i in enumerate(viewed):  # newest first
        out[i] = out.get(i, 0) + WEIGHTS["viewed"] * RECENCY**n
    return out


def suggest(db, favorites: list[int], compared: list[int], viewed: list[int], limit: int = 8, max_age: int | None = None, position: str | None = None) -> dict:
    ids, vectors = matrix(db)
    place = {p: n for n, p in enumerate(ids)}
    folk = data.people(db)
    seeds = {i: w for i, w in _seeds(favorites, compared, viewed).items() if i in place}
    known = set(favorites) | set(compared) | set(viewed)
    allowed = np.array([
        p not in known and p in folk.index and folk.at[p, "gp"] >= MIN_GAMES
        and (max_age is None or (folk.at[p, "age"] or 99) <= max_age) and (not position or position.lower() in folk.at[p, "position"].lower())
        for p in ids
    ])
    quality = np.array([(folk.at[p, "overall_score"] or 0) / 100 if p in folk.index else 0 for p in ids], dtype=float)
    if not seeds:
        return {"basis": "popular", "items": _starters(db, ids, vectors, allowed, quality, limit)}

    order = sorted(seeds, key=lambda i: -seeds[i])[:20]
    heaviest = seeds[order[0]]
    close = np.vstack([similarity(np.sqrt(((vectors - vectors[place[s]]) ** 2).sum(axis=1))) for s in order])  # seeds x players
    weight = np.array([np.sqrt(seeds[s] / heaviest) for s in order])
    weighted = close * weight[:, None]
    # Mostly the best single match; agreement with several seeds helps a little.
    top = np.sort(weighted, axis=0)[::-1]
    content = 0.8 * top[0] + 0.2 * top[: min(3, len(order))].mean(axis=0)
    # Where the audience of these players goes on to look, learned from everyone's views.
    together = np.zeros(len(ids))
    source: dict[int, int] = {}
    strongest = np.zeros(len(ids))
    learned = links(db, order)
    for s, w in zip(order, weight):
        for other, value in learned.get(s, {}).items():
            n = place.get(other)
            if n is not None:
                together[n] += w * value
                if w * value > strongest[n]:
                    strongest[n], source[n] = w * value, s
    if together.max() > 0:
        together /= np.sort(together)[-min(10, len(together)):].mean()  # about 1 for the best ten
        together = np.minimum(together, 1.5)
    share = AUDIENCE_SHARE if learned else 0.0
    allowed &= (close.max(axis=0) >= MIN_MATCH) | (together > 0.3)
    score = np.where(allowed, (0.9 - share) * content + share * together + 0.10 * quality, -1.0)

    chosen, per_seed = [], {}
    while len(chosen) < limit:
        penalty = np.max([similarity(np.sqrt(((vectors - vectors[c]) ** 2).sum(axis=1))) for c in chosen], axis=0) if chosen else 0
        value = np.where(score > 0, score - VARIETY * penalty, -1e9)
        value[chosen] = -1e9
        for seed, n in per_seed.items():
            if n >= PER_SEED and len(order) > 1:
                value[weighted.argmax(axis=0) == order.index(seed)] -= 0.5
        n = int(value.argmax())
        if value[n] <= -1e8:
            break
        chosen.append(n)
        best = order[int(weighted[:, n].argmax())]
        per_seed[best] = per_seed.get(best, 0) + 1
    items = []
    for n in chosen:
        seed = order[int(weighted[:, n].argmax())]
        alike = close[order.index(seed), n] >= MIN_MATCH
        if not alike and n in source:  # chosen for what people open, not for how he plays
            items.append({"player_id": ids[n], "because_of": None, "similarity": None, "shared": [], "also_viewed_with": source[n], "archetype": table(db).at[ids[n], "archetype"]})
            continue
        shared = [t for t in explain(db, seed, ids[n])["alike"] if t["high"]][:3]
        items.append({
            "player_id": ids[n], "because_of": seed, "similarity": float(close[order.index(seed), n]), "shared": [t["label"].lower().removeprefix("shots: ") for t in shared],
            "also_viewed_with": source.get(n) if together[n] > 0.3 else None, "archetype": table(db).at[ids[n], "archetype"],
        })
    return {"basis": "interests", "items": items}


def _starters(db, ids, vectors, allowed, quality, limit) -> list[dict]:
    """Nothing known about the person yet: strong players of different types."""
    frame = table(db)
    out, seen = [], set()
    for n in np.argsort(-quality, kind="stable"):
        kind = frame.at[ids[n], "archetype"]
        if not allowed[n] or kind in seen:
            continue
        seen.add(kind)
        out.append({"player_id": ids[n], "because_of": None, "similarity": None, "shared": [], "also_viewed_with": None, "archetype": kind})
        if len(out) == limit:
            break
    return out


def team_needs(db, team_id: int) -> dict[str, float]:
    """Minutes-weighted skills of a squad against the average squad, in standard deviations of teams."""
    folk = data.people(db)
    profiles = load_profiles(db)
    squads: dict[int, list[dict]] = {}
    for p, row in folk.iterrows():
        if p in profiles and row.team == row.team:
            squads.setdefault(int(row.team), []).append(profiles[p])
    means = {t: {k: float(np.average([p["z"][k] for p in squad], weights=[p["mins"] for p in squad])) for k in SKILLS} for t, squad in squads.items()}
    if team_id not in means:
        return {}
    return {k: (means[team_id][k] - np.mean([m[k] for m in means.values()])) / (np.std([m[k] for m in means.values()]) or 1) for k in SKILLS}


def team_targets(db, team_id: int, limit: int = 8, max_age: int | None = None, position: str | None = None) -> dict | None:
    """Players elsewhere who are strong where this team is weak."""
    needs = team_needs(db, team_id)
    if not needs:
        return None
    folk, profiles = data.people(db), load_profiles(db)
    # Scoring is left out: every star scores, and it would put the same names on every list.
    gaps = {k: max(0.0, -v) for k, v in needs.items() if k != "scoring"}
    total = sum(gaps.values()) or 1
    scored = []
    for p, profile in profiles.items():
        if p not in folk.index or folk.at[p, "team"] == team_id or profile["games"] < 30 or profile["mpg"] < 15:
            continue
        if max_age is not None and (folk.at[p, "age"] or 99) > max_age:
            continue
        if position and position.lower() not in folk.at[p, "position"].lower():
            continue
        fills = sum(g * profile["z"][k] for k, g in gaps.items()) / total
        reasons = sorted((k for k in gaps if gaps[k] > 0.3 and profile["z"][k] > 0.5), key=lambda k: -gaps[k] * profile["z"][k])[:3]
        if reasons:
            scored.append((fills + STAR_WEIGHT * profile["score"] / 100, p, reasons))
    scored.sort(key=lambda s: -s[0])
    picked, positions = [], {}
    for _, p, reasons in scored:
        kind = main_position(profiles[p])
        if not position and positions.get(kind, 0) >= max(2, limit // 2):
            continue
        positions[kind] = positions.get(kind, 0) + 1
        picked.append({"player_id": p, "score": profiles[p]["score"], "reasons": [SKILLS[k] for k in reasons]})
        if len(picked) == limit:
            break
    ranked = sorted(needs.items(), key=lambda kv: kv[1])
    return {"needs": [{"label": SKILLS[k], "z": float(v)} for k, v in ranked], "targets": picked}
