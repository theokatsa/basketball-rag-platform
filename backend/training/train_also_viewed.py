"""Train "users also viewed" and compare the methods.

    python training/train_also_viewed.py            compare on the past, then store lists for everyone
    python training/train_also_viewed.py --store    only retrain and store (for a nightly job)

The views are split by time: the first 70% of the period to learn from, the next 15% to choose
settings and to fit the blend, the last 15% only to report. Two tasks:
  A  next to a player: which others are opened in the same visit?
  B  for a person: which players will be opened for the first time?
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.services import audience_models as am  # noqa: E402
from app.services import league_data as data  # noqa: E402
from app.services.cache import rows  # noqa: E402
from app.services.similarity_service import matrix  # noqa: E402
from app.services.style_model import similarity  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "evaluation" / "results"
MODEL = Path(__file__).resolve().parent.parent / "models" / "also_viewed.json"
K, KEEP, HALF_LIFE = 6, 24, 60.0


def load():
    with SessionLocal() as db:
        views = pd.DataFrame(rows(db, text("select user_id, player_id, visit, viewed_at from player_views order by viewed_at")))
        folk = data.people(db)
        style_ids, vectors = matrix(db)
    ids = sorted(set(views.player_id) | set(folk.index))
    place = {p: n for n, p in enumerate(ids)}
    views["item"] = views.player_id.map(place)
    views["key"] = views.user_id.astype(str) + ":" + views.visit.astype(str)
    content = np.zeros((len(ids), len(ids)))
    where = [place[p] for p in style_ids]
    d = np.sqrt(((vectors[:, None, :] - vectors[None, :, :]) ** 2).sum(axis=2))
    content[np.ix_(where, where)] = similarity(d)
    np.fill_diagonal(content, 0)
    team = folk.team.reindex(ids).to_numpy()
    same = (team[:, None] == team[None, :]).astype(float)
    np.fill_diagonal(same, 0)
    return views, ids, content, np.nan_to_num(same)


def visits(views, size, now=None):
    """Visit x player, newer visits counting more (half after 60 days)."""
    now = now or views.viewed_at.max()
    key, _ = pd.factorize(views.key)
    x = np.zeros((key.max() + 1, size))
    age = (now - views.viewed_at).dt.total_seconds().to_numpy() / 86400
    np.maximum.at(x, (key, views.item.to_numpy()), np.sqrt(0.5 ** (np.maximum(age, 0) / HALF_LIFE)))
    return x


def person_matrix(views, size):
    user, names = pd.factorize(views.user_id)
    x = np.zeros((len(names), size))
    np.add.at(x, (user, views.item.to_numpy()), 1)
    return np.log1p(x) / np.log(2), list(names)


def live(views, size):
    """What the platform did so far: each user once per pair, over the root of both audiences."""
    pairs = {}
    for _, g in views.groupby(["user_id", "visit"]):
        items = g.item.unique()
        for a in items:
            for b in items:
                if a != b:
                    pairs.setdefault((a, b), set()).add(g.user_id.iloc[0])
    people = views.groupby("item").user_id.nunique().reindex(range(size)).fillna(0).to_numpy()
    m = np.zeros((size, size))
    for (a, b), users in pairs.items():
        m[a, b] = len(users) / np.sqrt(people[a] * people[b])
    return m


def queries(views):
    """(player, the others opened in that visit) for every visit with more than one player."""
    out = []
    for _, g in views.groupby("key"):
        items = g.item.unique()
        if len(items) > 1:
            out += [(a, [b for b in items if b != a]) for a in items]
    return out


def measure(ranked, truth, catalogue):
    """ranked: list of top-K lists; truth: list of sets."""
    recall, ndcg, hit, shown = [], [], [], set()
    for top, good in zip(ranked, truth):
        hits = [t in good for t in top]
        recall.append(sum(hits) / min(K, len(good)))
        ndcg.append(sum(h / np.log2(i + 2) for i, h in enumerate(hits)) / sum(1 / np.log2(i + 2) for i in range(min(K, len(good)))))
        hit.append(any(hits))
        shown.update(top)
    return {"recall": float(np.mean(recall)), "ndcg": float(np.mean(ndcg)), "hit": float(np.mean(hit)), "coverage": len(shown) / catalogue}


def rank_items(m, asked):
    """Top K of each asked row, without the player himself."""
    m = m.copy()
    np.fill_diagonal(m, -np.inf)
    top = np.argsort(-m, axis=1, kind="stable")[:, :K]
    return [list(top[a]) for a, _ in asked]


def methods(x, size, content, same, settings):
    return {
        "popularity": am.popularity(x), "same team": same + am.popularity(x) / 1e6, "similar players (no audience)": content, "Jaccard": am.jaccard(x), "cosine": am.cosine(x), "cosine, shrunk": am.cosine(x, settings["shrink"]),
        "PPMI": am.ppmi(x), "item2vec (PPMI + SVD)": am.item2vec(x, settings["size"]), "EASE": am.ease(x, settings["reg"]), "graph walk": am.walk(x, settings["restart"]),
    }


def backed(x, size, content, same, settings):
    """What people did (EASE), leaning on similarity and team where a player has few visits.

    trust = visits / (visits + k): with k visits the two count the same.
    """
    n = x.sum(axis=0)
    trust = (n / (n + settings["prior"]))[:, None]
    return trust * am.standardised(am.ease(x, settings["reg"])) + (1 - trust) * am.standardised(content + 0.5 * same)


BLEND = ["cosine, shrunk", "EASE", "graph walk", "item2vec (PPMI + SVD)", "similar players (no audience)", "same team", "popularity"]


def blend_features(found):
    return np.stack([am.standardised(found[name]) for name in BLEND])


def fit_blend(features, asked, size):
    """Weights that rank best on the validation period, by coordinate ascent on nDCG itself.

    A classifier of opened against random pairs was tried first: it mostly learned popularity and
    ranked worse than equal weights. Equal weights are the start here, so it cannot do worse on
    the period it is fitted to.
    """
    truth = [set(g) for _, g in asked]

    def quality(w):
        return measure(rank_items(np.tensordot(w, features, axes=1), asked), truth, size)["ndcg"]

    weights = np.ones(len(features))
    best = quality(weights)
    for _ in range(3):
        before = best
        for n in range(len(weights)):
            for value in (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
                trial = weights.copy()
                trial[n] = value
                if trial.any() and (q := quality(trial)) > best + 1e-5:
                    best, weights = q, trial
        if best - before < 1e-4:
            break
    return weights


def tune(x, asked, size):
    """Each setting on its own, by nDCG on the validation period."""
    truth = [set(g) for _, g in asked]

    def best(values, make):
        return max(values, key=lambda v: measure(rank_items(make(v), asked), truth, size)["ndcg"])

    return {
        "shrink": best([2, 8, 32, 64, 128, 256], lambda v: am.cosine(x, v)), "size": best([8, 16, 32, 48, 64, 96], lambda v: am.item2vec(x, v)),
        "reg": best([20, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800], lambda v: am.ease(x, v)), "restart": best([0.05, 0.1, 0.2, 0.3, 0.4, 0.6], lambda v: am.walk(x, v)),
    }


def person_task(train, test, size):
    """People with some history who open something new later: rows of the matrix and the truth."""
    pm, names = person_matrix(train, size)
    later = test.groupby("user_id").item.agg(set).to_dict()
    chosen, truth = [], []
    for n, user in enumerate(names):
        new = later.get(user, set()) - set(np.where(pm[n] > 0)[0])
        if new and (pm[n] > 0).sum() >= 3:
            chosen.append(n)
            truth.append(new)
    return pm, chosen, truth


def person_measure(pm, chosen, truth, scores, size):
    scores = np.where(pm[chosen] > 0, -np.inf, scores)
    return measure([list(r) for r in np.argsort(-scores, axis=1, kind="stable")[:, :K]], truth, size)


def people_like(pm, near):
    unit = pm / (np.linalg.norm(pm, axis=1, keepdims=True) + 1e-9)
    sim = unit @ unit.T
    np.fill_diagonal(sim, 0)
    keep = np.sort(sim, axis=1)[:, -min(near, len(sim) - 1)][:, None]
    return np.where(sim >= keep, sim, 0) @ (pm > 0)


def person_blend(pm, chosen, content, settings):
    """The scores used for suggestions: EASE over people, with some statistical similarity."""
    learned = am.standardised(pm[chosen] @ am.ease(pm, settings["person_reg"]))
    similar = am.standardised(np.stack([(content * row[:, None]).max(axis=0) for row in pm[chosen]]))
    return learned + settings["person_content"] * similar


def tune_person(train, valid, size, content):
    pm, chosen, truth = person_task(train, valid, size)
    regs = (10, 30, 100, 300, 1000, 3000)
    reg = max(regs, key=lambda r: person_measure(pm, chosen, truth, pm[chosen] @ am.ease(pm, r), size)["ndcg"])
    near = max((10, 20, 40, 80, 160), key=lambda k: person_measure(pm, chosen, truth, people_like(pm, k)[chosen], size)["ndcg"])
    shares = (0.0, 0.1, 0.2, 0.35, 0.5)
    share = max(shares, key=lambda c: person_measure(pm, chosen, truth, person_blend(pm, chosen, content, {"person_reg": reg, "person_content": c}), size)["ndcg"])
    return {"person_reg": reg, "person_near": near, "person_content": share}


def personal(train, test, size, item, content, settings):
    pm, chosen, truth = person_task(train, test, size)
    unit = pm / (np.linalg.norm(pm, axis=1, keepdims=True) + 1e-9)
    ways = {
        "popularity": np.tile(pm.sum(axis=0), (len(chosen), 1)), "similar players": np.stack([(content * row[:, None]).max(axis=0) for row in pm[chosen]]), "also viewed lists": unit[chosen] @ item,
        "people like you": people_like(pm, settings["person_near"])[chosen], "EASE over people": pm[chosen] @ am.ease(pm, settings["person_reg"]), "EASE + similar players (used)": person_blend(pm, chosen, content, settings),
    }
    return {how: person_measure(pm, chosen, truth, s, size) for how, s in ways.items()}, len(chosen)


def table(title, result):
    lines = [title, "", "| Method | Recall@6 | nDCG@6 | At least one right | Catalogue shown |", "|---|---|---|---|---|"]
    return "\n".join(lines + [f"| {k} | {v['recall']:.3f} | {v['ndcg']:.3f} | {v['hit']:.3f} | {v['coverage']:.2f} |" for k, v in result.items()])


def recovery(m, ids, truth=None):
    """Do the lists find the random storyline groups, which only behaviour can reveal?"""
    if truth is None:
        file = RESULTS / "simulation.json"
        if not file.exists():
            return None
        truth = json.loads(file.read_text(encoding="utf-8"))
    place = {p: n for n, p in enumerate(ids)}
    m = m.copy()
    np.fill_diagonal(m, -np.inf)
    top = np.argsort(-m, axis=1)[:, :K]
    shares = []
    for g in truth["groups"]:
        for p in g:
            others = {place[q] for q in g if q != p}
            shares.append(len(others & set(top[place[p]])) / min(K, len(others)))
    return float(np.mean(shares))


def bootstrap(a, b, seed=1):
    rng = np.random.default_rng(seed)
    d = np.asarray(a) - np.asarray(b)
    means = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    return float(d.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def single(ranked, truth):
    return [sum((t in g) / np.log2(i + 2) for i, t in enumerate(top)) / sum(1 / np.log2(i + 2) for i in range(min(K, len(g)))) for top, g in zip(ranked, truth)]


def compare(views, ids, content, same, truth_file=None):
    size = len(ids)
    start, end = views.viewed_at.min(), views.viewed_at.max()
    first, second = start + 0.70 * (end - start), start + 0.85 * (end - start)
    # A visit belongs to the period in which it began.
    begun = views.groupby("key").viewed_at.transform("min")
    train, valid, test = views[begun < first], views[(begun >= first) & (begun < second)], views[begun >= second]
    print(f"{len(train)} / {len(valid)} / {len(test)} views to learn, choose and test; {size} players")
    x = visits(train, size)
    asked_v = queries(valid)
    settings = tune(x, asked_v, size)
    settings |= tune_person(train, valid, size, content)
    print("settings chosen on the validation period:", settings)
    found = methods(x, size, content, same, settings)
    settings["prior"] = max((0.5, 1, 2, 4, 8, 16), key=lambda k: measure(rank_items(backed(x, size, content, same, settings | {"prior": k}), asked_v), [set(g) for _, g in asked_v], size)["ndcg"])
    print("prior:", settings["prior"])
    weights = fit_blend(blend_features(found), asked_v, size)
    # For the test everything is learned again from all earlier views; settings and weights stay.
    early = views[begun < second]
    x = visits(early, size)
    found = {"the platform so far": live(early, size), **methods(x, size, content, same, settings)}
    found["learned blend"] = np.tensordot(weights, blend_features(found), axes=1)
    found["EASE with prior (used)"] = backed(x, size, content, same, settings)
    found["equal blend"] = blend_features(found).mean(axis=0)
    asked = queries(test)
    truth = [set(g) for _, g in asked]
    result = {k: measure(rank_items(m, asked), truth, size) for k, m in found.items()}
    result = dict(sorted(result.items(), key=lambda kv: kv[1]["ndcg"]))
    print("\n" + table(f"A. Next to a player ({len(asked)} questions)", result))
    print("\nblend weights:", {n: round(float(w), 2) for n, w in zip(BLEND, weights)})
    a, b = single(rank_items(found["EASE with prior (used)"], asked), truth), single(rank_items(found["the platform so far"], asked), truth)
    gain = bootstrap(a, b)
    print(f"EASE with prior - platform so far: {gain[0]:+.3f} nDCG (95% interval {gain[1]:+.3f} to {gain[2]:+.3f})")
    others = {k: bootstrap(a, single(rank_items(found[k], asked), truth)) for k in ("EASE", "learned blend", "equal blend")}
    print({k: [round(v, 3) for v in o] for k, o in others.items()})
    found_groups = {k: recovery(found[k], ids, truth_file) for k in ("popularity", "similar players (no audience)", "the platform so far", "EASE", "EASE with prior (used)", "learned blend", "equal blend")}
    print("random storyline groups found in the top 6:", {k: round(v, 3) for k, v in found_groups.items() if v is not None})
    person, people = personal(early, test, size, found["EASE with prior (used)"] - found["EASE with prior (used)"].min(axis=1, keepdims=True), content, settings)
    print("\n" + table(f"B. For a person ({people} people with history and something new)", person))
    return settings, weights, {"also_viewed": result, "weights": dict(zip(BLEND, map(float, weights))), "settings": settings, "gain": gain, "against": others, "groups_found": found_groups, "personal": person}


def store(views, ids, content, same, settings):
    """The lists for every player, learned from all views."""
    size = len(ids)
    m = backed(visits(views, size), size, content, same, settings)
    np.fill_diagonal(m, -np.inf)
    people = views.groupby("item").user_id.nunique().reindex(range(size)).fillna(0).astype(int)
    together: dict[tuple, set] = {}
    for _, g in views.groupby("key"):
        items = g.item.unique()
        for a in items:
            for b in items:
                if a != b:
                    together.setdefault((a, b), set()).add(g.user_id.iloc[0])
    out = []
    for a in range(size):
        if people[a] == 0:
            continue  # nobody opened this player yet, so "also viewed" would be a claim without evidence
        for rank, b in enumerate(np.argsort(-m[a])[:KEEP], 1):
            out.append((ids[a], ids[b], rank, float(m[a, b]), len(together.get((a, b), ())), int(people[a])))
    b = am.ease(person_matrix(views, size)[0], settings["person_reg"])
    links = [(ids[i], ids[j], float(b[i, j])) for i in range(size) if people[i] for j in np.argsort(-b[i])[:KEEP * 2] if b[i, j] > 0]
    with engine.begin() as conn:
        conn.exec_driver_sql((Path(__file__).resolve().parent.parent / "scripts" / "schema_audience.sql").read_text(encoding="utf-8"))
        with conn.connection.cursor() as cursor:
            cursor.execute("delete from player_audience_links")
            execute_values(cursor, "insert into player_audience_links (player_id, other_id, weight) values %s", links, page_size=3000)
            cursor.execute("delete from player_also_viewed")
            execute_values(cursor, "insert into player_also_viewed (player_id, other_id, rank, score, viewers, audience) values %s", out, page_size=3000)
    print(f"stored {len(out)} visit pairs and {len(links)} person links for {len({o[0] for o in out})} players")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", action="store_true")
    parser.add_argument("--confirm", type=int, metavar="SEED", help="compare on a fresh simulation that is never stored")
    args = parser.parse_args()
    loaded = load()
    if args.confirm is not None:
        from scripts.simulate_users import simulate

        _, made, hidden = simulate(600, 60, args.confirm)
        fresh = pd.DataFrame(made, columns=["user_id", "player_id", "visit", "viewed_at"])
        place = {p: n for n, p in enumerate(loaded[1])}
        fresh["item"], fresh["key"] = fresh.player_id.map(place), fresh.user_id.astype(str) + ":" + fresh.visit.astype(str)
        fresh["viewed_at"] = pd.to_datetime(fresh.viewed_at)
        _, _, report = compare(fresh, *loaded[1:], hidden)
        (RESULTS / f"also_viewed_confirm_{args.confirm}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        raise SystemExit
    if args.store:
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        settings = model["settings"]
    else:
        settings, weights, report = compare(*loaded)
        MODEL.write_text(json.dumps({"settings": settings}, indent=1), encoding="utf-8")
        (RESULTS / "also_viewed.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    store(*loaded, settings)
