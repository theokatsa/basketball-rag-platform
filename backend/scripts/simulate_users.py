"""Fill the platform with simulated users, so that audience features can be built and tested.

    python scripts/simulate_users.py              600 users, 60 days (replaces earlier simulated ones)
    python scripts/simulate_users.py --remove     take every simulated user and view out again

Simulated accounts are flagged (app_users.is_simulated), have an address that cannot exist and a
password nobody can know. Real accounts and their views are never touched.

What drives a click, on average:
  fan 35%        players of a favourite team
  storyline 20%  one of 25 random groups of players (a draft class, a podcast, a trade rumour);
                 random, so nothing but behaviour can reveal them
  star 20%       popularity, part of which is pure chance
  scout 13%      a position and age group
  similar 12%    the site's own "similar players" list
plus a few players who are suddenly in the news. The truth is saved for checking what is recovered.
"""

import argparse
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.services import league_data as data  # noqa: E402
from app.services.similarity_service import matrix  # noqa: E402

TRUTH = Path(__file__).resolve().parent.parent / "evaluation" / "results" / "simulation.json"
SOURCES = ["fan", "storyline", "star", "scout", "similar"]
MIX = np.array([0.35, 0.20, 0.20, 0.13, 0.12])
STAY = 0.65  # chance that the next click has the same reason as the last
GROUPS, EVENTS_PAST, EVENTS_NOW = 25, 6, 4
EVENT_SHARE = 0.04  # of clicks while something is in the news


def schema():
    with engine.begin() as conn:
        conn.exec_driver_sql((Path(__file__).parent / "schema_audience.sql").read_text(encoding="utf-8"))


def remove() -> int:
    with engine.begin() as conn:
        return conn.exec_driver_sql("delete from app_users where is_simulated").rowcount  # views go with them


def pick(rng, ids, weights):
    total = weights.sum()
    return int(ids[rng.choice(len(ids), p=weights / total)]) if total > 0 else int(rng.choice(ids))


def simulate(users: int, days: int, seed: int):
    rng = np.random.default_rng(seed)
    with SessionLocal() as db:
        folk = data.people(db)
        style_ids, vectors = matrix(db)
        teams = list(data.team_list(db).index)
    folk = folk[folk.gp >= 5]
    ids = folk.player_id.to_numpy()
    score = folk.overall_score.fillna(0).to_numpy(dtype=float)
    # Popularity follows quality only in part; the rest is chance that no statistic explains.
    fame = np.exp(1.5 * (score - score.mean()) / score.std() + 0.6 * rng.normal(size=len(ids)))
    minutes = folk.mpg.to_numpy(dtype=float)
    team = folk.team.fillna(0).to_numpy(dtype=int)
    place = {int(p): n for n, p in enumerate(ids)}
    near = {}
    for n, p in enumerate(style_ids):
        d = ((vectors - vectors[n]) ** 2).sum(axis=1)
        near[p] = [style_ids[j] for j in d.argsort()[1:7] if style_ids[j] in place]

    groups = []
    for _ in range(GROUPS):
        size = int(rng.integers(5, 9))
        groups.append([int(x) for x in rng.choice(ids, size=size, replace=False, p=fame**0.4 / (fame**0.4).sum())])
    now = datetime.now(timezone.utc).replace(microsecond=0)
    events = []
    for k in range(EVENTS_PAST + EVENTS_NOW):
        ago = float(rng.uniform(12, days - 8)) if k < EVENTS_PAST else float(rng.uniform(1, 5))
        events.append({"player_id": int(rng.choice(ids[(fame < np.quantile(fame, 0.9)) & (fame > np.quantile(fame, 0.4))])), "start": (now - timedelta(days=ago)).isoformat(), "days": 5, "now": k >= EVENTS_PAST})

    market = np.exp(rng.normal(0, 0.6, len(teams)))
    records, views = [], []
    for u in range(users):
        mix = rng.dirichlet(MIX * 6)
        team_of = int(rng.choice(teams, p=market / market.sum()))
        mine = [groups[g] for g in rng.choice(GROUPS, size=int(rng.integers(1, 3)), replace=False)]
        role = str(rng.choice(["Guard", "Forward", "Center"]))
        oldest = int(rng.choice([23, 26, 45]))
        wanted = np.array([role in p for p in folk.position]) & (folk.age.fillna(99).to_numpy() <= oldest)
        weights = {
            "fan": np.where(team == team_of, fame**0.5 * minutes, 0), "star": fame**1.2, "scout": np.where(wanted, fame**0.4, 0),
        }
        joined = now - timedelta(days=float(rng.uniform(3, days)))
        span = (now - joined).total_seconds() / 86400
        visits = int(min(60, 1 + rng.pareto(1.3) * 4 * span / days + rng.poisson(3 * span / days)))
        stamps = sorted(joined + timedelta(days=float(x)) for x in rng.uniform(0, span, visits))
        # People come in the evening; visits must stay apart to count as separate.
        stamps = sorted((s.replace(hour=int(np.clip(rng.normal(19, 4), 6, 23)), minute=int(rng.integers(0, 60))) for s in stamps))
        stamps = [s for n, s in enumerate(stamps) if s < now - timedelta(hours=1) and (n == 0 or s - stamps[n - 1] > timedelta(hours=2))]
        opened: dict[int, int] = {}
        for number, start in enumerate(stamps, 1):
            when, seen, source = start, [], None
            story = mine[int(rng.integers(len(mine)))]
            for _ in range(int(min(12, 1 + rng.geometric(0.28)))):
                if source is None or rng.random() > STAY:
                    source = str(rng.choice(SOURCES, p=mix))
                live = [e for e in events if datetime.fromisoformat(e["start"]) <= when <= datetime.fromisoformat(e["start"]) + timedelta(days=e["days"])]
                if live and rng.random() < EVENT_SHARE * min(3, len(live)):
                    player = live[int(rng.integers(len(live)))]["player_id"]
                elif source == "storyline":
                    player = int(rng.choice(story))
                elif source == "similar" and seen and near.get(seen[-1]):
                    options = near[seen[-1]]
                    player = int(options[min(len(options) - 1, int(rng.geometric(0.4)) - 1)])
                else:
                    player = pick(rng, ids, weights["star" if source == "similar" else source])
                if player in seen:
                    continue
                seen.append(player)
                views.append((u, player, number, when))
                opened[player] = opened.get(player, 0) + 1
                when += timedelta(seconds=float(rng.gamma(2, 40)))
        favorites = [p for p, n in opened.items() if rng.random() < min(0.6, 0.06 + 0.16 * (n - 1))]
        history = [v[1] for v in views if v[0] == u][::-1]
        state = {"favorites": favorites, "groups": {}, "history": list(dict.fromkeys(history))[:12], "notes": {}}
        records.append((f"sim-{u + 1:04d}@simulated.invalid", f"Simulated user {u + 1}", f"scrypt${secrets.token_hex(16)}${secrets.token_hex(32)}", json.dumps(state), joined))
    return records, views, {"seed": seed, "created": now.isoformat(), "groups": groups, "events": events}


def store(records, views, truth):
    with engine.begin() as conn:
        conn.exec_driver_sql("set local statement_timeout = 0")
        with conn.connection.cursor() as cursor:
            cursor.execute("delete from app_users where is_simulated")
            made = execute_values(
                cursor, "insert into app_users (email, display_name, password_hash, state, created_at, is_simulated) values %s returning id, email",
                records, template="(%s,%s,%s,%s::jsonb,%s,true)", page_size=1000, fetch=True,
            )
            number = {email: i for i, email in made}
            execute_values(cursor, "insert into player_views (user_id, player_id, visit, viewed_at) values %s", [(number[records[u][0]], p, v, t) for u, p, v, t in views], page_size=5000)
    TRUTH.write_text(json.dumps(truth, indent=1), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--users", type=int, default=600)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    schema()
    if args.remove:
        print(f"removed {remove()} simulated users; run training/train_also_viewed.py to update the lists")
    else:
        records, views, truth = simulate(args.users, args.days, args.seed)
        store(records, views, truth)
        sizes = np.bincount([v[0] for v in views], minlength=len(records))
        print(f"{len(records)} users, {len(views)} views of {len({v[1] for v in views})} players; views per user: median {int(np.median(sizes))}, most {sizes.max()}")
