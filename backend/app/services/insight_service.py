"""Transparent, statistics-only judgements: why players match, who fits, who is hard to face.

Nothing here is a trained model. Every figure is a weighted mix of stored statistics, and
small samples are pulled toward the league (or the player's own) average.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import text

from app.services.cache import cached, rows
from app.services.stat_vectors import FEATURES
from app.core.config import ACTIVE_SEASON_SQL

LATEST = ACTIVE_SEASON_SQL
MIN_POOL_GAMES, MIN_POOL_MINUTES = 20, 12
MATCHUP_PRIOR = 60  # possessions at the player's own average added to every matchup
USAGE_COST = 0.6  # points per possession lost per unit of extra usage: one usage point costs 0.6 points per 100 (a cautious value)

_PROFILE = text(f"""
    with box as (
        select player_id, count(*) as games, sum(minutes) as mins, sum(points) as pts, sum(fgm) as fgm, sum(fga) as fga,
               sum(tpm) as tpm, sum(tpa) as tpa, sum(ftm) as ftm, sum(fta) as fta, sum(oreb) as oreb, sum(dreb) as dreb,
               sum(ast) as ast, sum(stl) as stl, sum(blk) as blk, sum(tov) as tov
        from player_box_scores where season = {LATEST} group by player_id
    )
    select b.*, p.full_name, t.nba_team_id, pp.position, pp.height,
           a.ast_pct, a.oreb_pct, a.dreb_pct, a.usg_pct, a.possessions, a.defended_fga, a.defended_fg_diff
    from box b
    join players p on p.id = b.player_id
    join player_advanced_stats a on a.player_id = b.player_id and a.season = {LATEST}
    left join player_season_stats s on s.player_id = b.player_id and s.season = {LATEST}
    left join teams t on t.id = s.team_id
    left join player_profiles pp on pp.player_id = b.player_id
""")

# Skill -> how it reads in a sentence.
SKILLS = {
    "scoring": "scoring", "efficiency": "efficient shooting", "spacing": "three-point shooting", "playmaking": "passing",
    "ball_security": "taking care of the ball", "offensive_boards": "offensive rebounding", "defensive_boards": "defensive rebounding",
    "steals": "steals", "rim_protection": "shot blocking", "shot_defense": "contesting shots", "free_throws": "drawing fouls",
}


def inches(height: str | None) -> int | None:
    try:
        feet, inch = (height or "").split("-")
        return int(feet) * 12 + int(inch)
    except ValueError:
        return None


def primary(p: dict) -> set[str]:
    return set((p["position"] or "").split("-")) - {""}


def main_position(p: dict) -> str:
    return (p["position"] or "").split("-")[0]


def load_profiles(db) -> dict[int, dict]:
    def load():
        people = [{k: (int(v) if hasattr(v, "as_tuple") else v) for k, v in r.items()} for r in rows(db, _PROFILE)]
        people = [p for p in people if p["mins"]]

        def total(key):
            return sum(p[key] or 0 for p in people)

        league_three = total("tpm") / total("tpa")
        league_ts = total("pts") / (2 * (total("fga") + 0.44 * total("fta")))
        league_ppu = total("pts") / (total("fga") + 0.44 * total("fta") + total("tov"))
        for p in people:
            minutes = p["mins"]
            p["mpg"] = minutes / p["games"]
            p["used"] = p["fga"] + 0.44 * p["fta"] + p["tov"]
            p["ppu"] = (p["pts"] + 100 * league_ppu) / (p["used"] + 100)
            p["ts"] = (p["pts"] + 120 * league_ts) / (2 * (p["fga"] + 0.44 * p["fta"]) + 120)
            p["three"] = (p["tpm"] + 60 * league_three) / (p["tpa"] + 60)
            p["inches"] = inches(p["height"])
            dfga = p["defended_fga"] or 0
            p["dfg_diff"] = (p["defended_fg_diff"] or 0) * dfga / (dfga + 250)
            poss = p["possessions"] or 0
            p["dfga100"] = dfga / poss * 100 if poss else 0

            def per36(key):
                return p[key] / minutes * 36

            p["raw"] = {
                "scoring": per36("pts"), "efficiency": p["ts"], "spacing": per36("tpa") * (p["three"] - 0.28), "playmaking": p["ast_pct"] or 0,
                "ball_security": -(p["tov"] / p["used"] if p["used"] else 0.13), "offensive_boards": p["oreb_pct"] or 0, "defensive_boards": p["dreb_pct"] or 0,
                "steals": per36("stl"), "rim_protection": per36("blk"), "shot_defense": -p["dfg_diff"], "free_throws": per36("fta"),
            }
        pool = [p for p in people if p["games"] >= MIN_POOL_GAMES and p["mpg"] >= MIN_POOL_MINUTES]
        for key in SKILLS:
            values = np.array([p["raw"][key] for p in pool])
            mean, spread = values.mean(), values.std() or 1
            for p in people:
                p.setdefault("z", {})[key] = float(np.clip((p["raw"][key] - mean) / spread, -3, 3))
        for p in people:
            z = p["z"]
            # Points above average per 100 possessions from shooting, plus creation and second chances.
            shooting = ((p["usg_pct"] or 0) * 100) * 2 * (p["ts"] - league_ts)
            p["offense"] = 0.7 * shooting + 1.1 * z["playmaking"] + 0.5 * z["spacing"] + 1.1 * z["scoring"] + 0.3 * z["ball_security"] + 0.3 * z["offensive_boards"]
            p["defense"] = 1.1 * z["shot_defense"] + 0.6 * z["steals"] + 0.6 * z["rim_protection"] + 0.5 * z["defensive_boards"]
            p["overall"] = p["offense"] + 0.8 * p["defense"] + 0.12 * (p["mpg"] - 24)  # coaches play good players more
        for key, out in (("offense", "offense_score"), ("defense", "defense_score"), ("overall", "score")):
            ordered = np.sort([p[key] for p in pool])
            for p in people:
                p[out] = int(round(100 * float(np.searchsorted(ordered, p[key], side="right")) / len(ordered)))
        return {p["player_id"]: p for p in people}

    return cached("profiles", load)


def _baselines(db) -> dict[int, float]:
    """Each scorer's own points per matchup possession."""
    sql = text(f"select off_player_id, (sum(points) / sum(possessions))::float as v from player_matchups where season = {LATEST} group by 1")
    return cached("matchup_base", lambda: {r["off_player_id"]: r["v"] for r in rows(db, sql)})


def _edge(points, possessions, base):
    """Shrunk difference to the scorer's own average, per 100 possessions."""
    return ((points + MATCHUP_PRIOR * base) / (possessions + MATCHUP_PRIOR) - base) * 100


def defenders(db, player_id: int):
    """Who guarded this player, and who this player guarded, with points per 100 possessions."""
    def load():
        profiles, bases = load_profiles(db), _baselines(db)
        own = bases.get(player_id)
        result = {"baseline": own * 100 if own else None, "guarded_by": [], "guarded": []}
        for column, other, out in (("off_player_id", "def_player_id", "guarded_by"), ("def_player_id", "off_player_id", "guarded")):
            found = rows(db, text(f"""
                select {other} as other_id, games, possessions, points, fgm, fga, tpm, tpa, tov, blk, ast, seconds
                from player_matchups where {column} = :id and season = {LATEST} order by possessions desc
            """), {"id": player_id})
            for m in found:
                base = own if out == "guarded_by" else bases.get(m["other_id"])
                if base is None or m["other_id"] not in profiles:
                    continue
                m["per100"] = m["points"] / m["possessions"] * 100
                m["edge"] = _edge(m["points"], m["possessions"], base)
                m["expected"] = base * 100
                result[out].append(m)
        return result

    return cached(("defenders", player_id), load)


def head_to_head(db, ids: list[int]):
    """Every tracked matchup between these players, with the scorer's usual rate against anyone."""
    base = _baselines(db)
    found = rows(db, text(f"""
        select off_player_id, def_player_id, games, seconds, possessions, points, fgm, fga, tpm, tpa, ftm, fta, ast, tov, blk
        from player_matchups where season = {LATEST} and off_player_id = any(:ids) and def_player_id = any(:ids)
    """), {"ids": ids})
    return [{**r, "usual": base[r["off_player_id"]] * 100} for r in found]


def _reasons(needs: dict, candidate: dict, limit=3):
    gains = sorted(((max(0, -needs[k]) + 0.25) * candidate["z"][k], k) for k in SKILLS if k != "scoring" and candidate["z"][k] > 0.5)
    return [SKILLS[k] for _, k in gains[::-1][:limit]]


def player_fit(db, player_id: int):
    def load():
        profiles = load_profiles(db)
        me = profiles.get(player_id)
        if me is None:
            return None
        needs = me["z"]
        candidates = []
        for p in profiles.values():
            if p["player_id"] == player_id or p["games"] < 35 or p["mpg"] < 20 or p["nba_team_id"] == me["nba_team_id"]:
                continue
            fills = sum(max(0, -needs[k]) * p["z"][k] for k in SKILLS if k != "scoring") / 3
            # Two ball-dominant players would take turns.
            overlap = 14 * max(0, (me["usg_pct"] or 0.2) + (p["usg_pct"] or 0.2) - 0.50)
            same = 0.9 if primary(me) == primary(p) else 0
            spacing = 0.35 * p["z"]["spacing"] if needs["spacing"] < 0 else 0
            candidates.append((0.4 * p["overall"] + fills + spacing - overlap - same, p))
        candidates.sort(key=lambda c: -c[0])
        ideal = [{"player_id": p["player_id"], "score": p["score"], "usage": (p["usg_pct"] or 0) * 100, "reasons": _reasons(needs, p)} for _, p in candidates[:6]]
        pairs = rows(db, text(f"""
            select case when player_a = :id then player_b else player_a end as other_id, nba_team_id, games, minutes, net_rating, off_rating, def_rating
            from player_pairs where season = {LATEST} and (player_a = :id or player_b = :id) and minutes >= 200
            order by net_rating desc
        """), {"id": player_id})
        matchups = defenders(db, player_id)
        faced = [m for m in matchups["guarded_by"] if m["possessions"] >= 25]
        held = [m for m in matchups["guarded"] if m["possessions"] >= 25]
        teams = rows(db, text(f"""
            select o.nba_team_id as team_id, count(*) as games, avg(b.points)::float as points, avg(b.reb)::float as rebounds, avg(b.ast)::float as assists,
                   (sum(b.points) / nullif(2 * (sum(b.fga) + 0.44 * sum(b.fta)), 0) * 100)::float as ts, avg(b.plus_minus)::float as plus_minus,
                   avg(b.points + 0.4 * b.fgm - 0.7 * b.fga - 0.4 * (b.fta - b.ftm) + 0.7 * b.oreb + 0.3 * b.dreb + b.stl + 0.7 * b.ast + 0.7 * b.blk - 0.4 * b.pf - b.tov)::float as game_score
            from player_box_scores b
            join team_box_scores o on o.nba_game_id = b.nba_game_id and o.nba_team_id <> b.nba_team_id
            where b.player_id = :id and b.season = {LATEST} and b.minutes >= 5
            group by 1 having count(*) >= 2 order by game_score desc
        """), {"id": player_id})
        return {
            "scores": {"overall": me["score"], "offense": me["offense_score"], "defense": me["defense_score"]},
            "skills": [{"key": k, "label": SKILLS[k], "z": needs[k]} for k in SKILLS],
            "ideal_teammates": ideal,
            "pairs": pairs,
            "toughest_defenders": sorted(faced, key=lambda m: m["edge"])[:6],
            "easiest_defenders": sorted(faced, key=lambda m: -m["edge"])[:6],
            "best_stops": sorted(held, key=lambda m: m["edge"])[:6],
            "worst_stops": sorted(held, key=lambda m: -m["edge"])[:6],
            "teams": teams,
            "baseline": matchups["baseline"],
        }

    return cached(("fit", player_id), load)


_FEATURE_LABELS = {
    "minutes": ("Minutes", 1), "points": ("Points", 1), "rebounds": ("Rebounds", 1), "assists": ("Assists", 1), "steals": ("Steals", 1),
    "blocks": ("Blocks", 1), "turnovers": ("Turnovers", 1), "field_goal_pct": ("Field goal %", 100), "three_point_attempts": ("Threes attempted", 1),
    "three_point_shrunk": ("Three-point % (adjusted)", 100), "free_throw_attempts": ("Free throws attempted", 1), "free_throw_shrunk": ("Free throw % (adjusted)", 100),
}


def explain_similarity(vectors, a: int, b: int) -> dict:
    """Which numbers bring two players together and which keep them apart."""
    i, j = vectors.index[a], vectors.index[b]
    items = []
    for n, name in enumerate(FEATURES):
        label, scale = _FEATURE_LABELS[name]
        za, zb = float(vectors.z[i][n]), float(vectors.z[j][n])
        items.append({
            "label": label, "percent": scale == 100, "own": float(vectors.rows[i][name] or 0) * scale, "other": float(vectors.rows[j][name] or 0) * scale,
            "gap": abs(za - zb), "shared": (min(abs(za), abs(zb)) if za * zb > 0 else 0) - abs(za - zb), "closeness": max(0.0, 1 - abs(za - zb) / 2),
        })
    # Distinctive numbers both players share come first; matching on an average number says little.
    alike = sorted(items, key=lambda d: -d["shared"])[:4]
    apart = [d for d in sorted(items, key=lambda d: -d["gap"]) if d["gap"] >= 0.5 and d not in alike][:3]

    def slim(d):
        return {k: d[k] for k in ("label", "percent", "own", "other", "closeness")}

    return {"alike": [slim(d) for d in alike], "apart": [slim(d) for d in apart]}


def analyze_lineup(db, ids: list[int]):
    profiles = load_profiles(db)
    five = [profiles[i] for i in dict.fromkeys(ids) if i in profiles]
    if len(five) != 5:
        return None
    people = list(profiles.values())
    weight = np.array([p["mins"] for p in people], dtype=float)
    league = cached("league_rating", lambda: rows(db, text(f"select (100 * sum(points) / sum(fga + 0.44 * fta - oreb + tov))::float as v from team_box_scores where season = {LATEST}"))[0]["v"])

    def mean(pick):
        return float(np.average([pick(p) or 0 for p in people], weights=weight))

    def add(pick):
        return sum(pick(p) or 0 for p in five)

    def base(pick):
        return 5 * mean(pick)

    def per100(key):
        return lambda p: p[key] / p["possessions"] * 100 if p["possessions"] else 0

    # Offense: one ball, so five usage rates are scaled to 100% and efficiency moves the other way.
    total_usage = sum(p["usg_pct"] or 0.2 for p in five)
    shares, chance_points = [], 0.0
    for p in five:
        own = p["usg_pct"] or 0.2
        share = own / total_usage
        efficiency = p["ppu"] - USAGE_COST * (share - own)
        chance_points += share * efficiency
        shares.append({"player_id": p["player_id"], "own": own * 100, "in_lineup": share * 100, "points_per_100": efficiency * 100, "own_points_per_100": p["ppu"] * 100, "weight": share})
    used_total = sum(p["used"] for p in people)
    league_ppu = sum(p["pts"] for p in people) / used_total
    # Teammates chase the same rebounds, so only part of an individual edge carries over.
    oreb, oreb0 = add(lambda p: p["oreb_pct"]), base(lambda p: p["oreb_pct"])
    dreb, dreb0 = add(lambda p: p["dreb_pct"]), base(lambda p: p["dreb_pct"])
    boards_o, boards_d = 0.6 * (oreb - oreb0), 0.45 * (dreb - dreb0)
    contest = add(lambda p: p["dfg_diff"] * p["dfga100"]) - base(lambda p: p["dfg_diff"] * p["dfga100"])
    steals = add(per100("stl")) - base(per100("stl"))
    offense = league + (chance_points - league_ppu) * 100 * 0.9 + boards_o * 55
    defense = league + contest * 2.1 * 0.8 - steals * 0.8 - boards_d * 55

    mix = list(zip(shares, five))
    tries = add(lambda p: p["tpa"] / p["mins"])
    # label, lineup value, average lineup, higher is better, what counts as a clear gap, note
    lines = [
        ("True shooting %", 100 * sum(s["weight"] * p["ts"] for s, p in mix), 100 * mean(lambda p: p["ts"]), True, 1.5, "Weighted by who would take the shots"),
        ("Three-point %", 100 * add(lambda p: p["tpa"] / p["mins"] * p["three"]) / max(tries, 1e-6), 100 * sum(p["tpm"] for p in people) / sum(p["tpa"] for p in people), True, 1.2, "Small samples pulled toward average"),
        ("Threes attempted per 100", add(per100("tpa")) / total_usage, base(per100("tpa")), True, 5, "Scaled down because the five share one ball"),
        ("Free throws per 100", add(per100("fta")) / total_usage, base(per100("fta")), True, 3, "Scaled down because the five share one ball"),
        ("Assist rate", 100 * add(lambda p: p["ast_pct"]), 100 * base(lambda p: p["ast_pct"]), True, 10, "Share of teammates' baskets each player assists, added up"),
        ("Turnovers per 100 uses", 100 * sum(s["weight"] * (p["tov"] / p["used"] if p["used"] else 0.12) for s, p in mix), 100 * sum(p["tov"] for p in people) / used_total, False, 1, "Weighted by usage"),
        ("Offensive rebound %", 100 * (oreb0 + boards_o), 100 * oreb0, True, 2, "Discounted: teammates chase the same rebounds"),
        ("Defensive rebound %", 100 * (dreb0 + boards_d), 100 * dreb0, True, 2.5, "Discounted: teammates chase the same rebounds"),
        ("Steals per 100", add(per100("stl")), base(per100("stl")), True, 1, ""),
        ("Blocks per 100", add(per100("blk")), base(per100("blk")), True, 1.2, ""),
        ("Contested shots", contest, 0.0, False, 0.8, "Extra baskets allowed per 100 possessions when contesting; below zero is good"),
    ]
    stats = [{"label": label, "own": own, "base": other, "higher": higher, "note": note, "z": (own - other) / gap * (1 if higher else -1)} for label, own, other, higher, gap, note in lines]

    shooters = [p["player_id"] for p in five if p["tpa"] / p["mins"] * 36 >= 4 and p["three"] >= 0.35]
    creators = [p["player_id"] for p in five if (p["ast_pct"] or 0) >= 0.20]
    protectors = [p["player_id"] for p in five if p["z"]["rim_protection"] >= 1]
    checks = [
        {"label": "Shooters", "target": 3, "players": shooters, "note": "At least 4 threes per 36 minutes at 35% or better"},
        {"label": "Creators", "target": 2, "players": creators, "note": "Assist on 20% or more of teammates' baskets"},
        {"label": "Rim protectors", "target": 1, "players": protectors, "note": "Blocks at least one deviation above average"},
    ]
    pairs = rows(db, text(f"""
        select player_a, player_b, sum(minutes)::float as minutes, (sum(net_rating * minutes) / sum(minutes))::float as net_rating
        from player_pairs where season = {LATEST} and player_a = any(:ids) and player_b = any(:ids) and minutes > 0
        group by 1, 2 having sum(minutes) >= 50
    """), {"ids": ids})
    heights = [p["inches"] for p in five if p["inches"]]
    return {
        "offense": offense, "defense": defense, "net": offense - defense, "league": league, "total_usage": total_usage * 100,
        "shares": shares, "stats": stats, "checks": checks, "pairs": pairs,
        "average_height": sum(heights) / len(heights) if heights else None,
        "opponents": _opponents(db, five, profiles),
    }


def _opponents(db, five, profiles):
    """For each player: the hardest and easiest opponents at the same position."""
    ids = [p["player_id"] for p in five]
    bases = _baselines(db)
    met = {(m["off_player_id"], m["def_player_id"]): m for m in rows(db, text(f"""
        select off_player_id, def_player_id, possessions, points from player_matchups
        where season = {LATEST} and (off_player_id = any(:ids) or def_player_id = any(:ids))
    """), {"ids": ids})}
    spread = float(np.std([p["overall"] for p in profiles.values() if p["mpg"] >= 20])) or 1

    def edge(off, guard):
        m = met.get((off, guard))
        return _edge(m["points"], m["possessions"], bases[off]) if m and off in bases else 0.0

    used = set(ids)
    out = []
    for p in five:
        me = p["player_id"]
        scored = []
        for o in profiles.values():
            other = o["player_id"]
            if other in used or o["games"] < 40 or o["mpg"] < 24 or main_position(o) != main_position(p):
                continue
            size = ((o["inches"] or 78) - (p["inches"] or 78)) * 0.08
            scored.append((o["overall"] / spread + (edge(other, me) - edge(me, other)) / 10 + size, o))
        scored.sort(key=lambda s: s[0])

        def describe(o):
            used.add(o["player_id"])
            notes = [f"Offense {o['offense_score']}, defense {o['defense_score']} out of 100"]
            faced, guarded = met.get((me, o["player_id"])), met.get((o["player_id"], me))
            if faced and faced["possessions"] >= 15:
                notes.append(f"{p['full_name']} scored {faced['points'] / faced['possessions'] * 100:.0f} per 100 when guarded ({faced['possessions']:.0f} possessions)")
            if guarded and guarded["possessions"] >= 15:
                notes.append(f"Scored {guarded['points'] / guarded['possessions'] * 100:.0f} per 100 against {p['full_name']} ({guarded['possessions']:.0f} possessions)")
            if o["inches"] and p["inches"] and abs(o["inches"] - p["inches"]) >= 2:
                gap = o["inches"] - p["inches"]
                notes.append(f"{abs(gap)} inches {'taller' if gap > 0 else 'shorter'}")
            return {"player_id": o["player_id"], "notes": notes}

        out.append({"player_id": me, "toughest": [describe(o) for _, o in scored[::-1][:2]], "easiest": [describe(o) for _, o in scored[:2] if o["player_id"] not in used]})
    return out
