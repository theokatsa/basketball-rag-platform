"""Compare ways of measuring player similarity, then train and store the best.

    python training/train_similarity.py

There is no answer key for "similar", so the test is identification: each player is described
twice, from two separate halves of the games, and a method is good when a player's closest
match among everyone is his own other half. Two checks keep that honest:
  * the learned method is always tested on players it was not trained on (5 folds)
  * it is trained on odd and even games but also tested on first against second half of the
    season, when roles change
Position agreement (do the five nearest share the main position?) is never trained on.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.services import league_data as data  # noqa: E402
from app.services.cache import rows  # noqa: E402
from app.services.shot_service import ZONE_SQL  # noqa: E402
from app.services.stat_vectors import load_season  # noqa: E402
from app.services.style_model import FEATURES, MODEL_FILE, NAMES, STYLE, features, learn, qualified  # noqa: E402

FOLDS, SEED = 5, 3
OLD = ["minutes", "points", "reb", "ast", "stl", "blk", "tov"]


def load():
    with SessionLocal() as db:
        box = data.box_scores(db)
        folk = data.people(db)
        shots = pd.DataFrame(rows(db, text(f"""
            select sc.player_id, sc.nba_game_id as game_id, {ZONE_SQL} as zone, sc.action_type as action, count(*) as tries, sum(sc.shot_distance) as feet
            from shot_charts sc where sc.season = {data.SEASON} and sc.player_id is not null group by 1, 2, 3, 4""")))
        load_season(db)
    return box, shots, folk


def sums(box):
    out = box.groupby("player_id")[data.SUMS].sum().astype(float)
    out["gp"] = box.groupby("player_id").size()
    return out


def old_vectors(s):
    """The twelve statistics the platform used before."""
    out = pd.DataFrame({c: s[c] / s.gp for c in OLD})
    total = s.sum()
    out["fg"] = s.fgm / s.fga.clip(lower=1)
    out["tpa"], out["fta"] = s.tpa / s.gp, s.fta / s.gp
    out["tp"] = (s.tpm + 50 * total.tpm / total.tpa) / (s.tpa + 50)
    out["ft"] = (s.ftm + 30 * total.ftm / total.fta) / (s.fta + 30)
    return out


def standardise(a, b):
    both = np.vstack([a, b])
    mean, spread = both.mean(axis=0), both.std(axis=0)
    spread[spread == 0] = 1
    return [np.clip((x - mean) / spread, -4, 4) for x in (a, b)]


def identify(a, b, only=None):
    """Rank of each player's own other half among all other halves, both ways."""
    d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2))
    own = np.diag(d)
    ranks = np.concatenate([(d < own[:, None]).sum(axis=1), (d < own[None, :]).sum(axis=0)])
    if only is not None:
        ranks = np.concatenate([ranks[: len(a)][only], ranks[len(a):][only]])
    return ranks


def agreement(x, positions, k=5, only=None):
    d = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    near = d.argsort(axis=1)[:, :k]
    hits = (positions[near] == positions[:, None]).mean(axis=1)
    return hits if only is None else hits[only]


def halves(box, shots, how):
    box = box.sort_values(["game_date", "game_id"])
    n = box.groupby("player_id").cumcount()
    size = box.groupby("player_id").game_id.transform("size")
    part = (n % 2 if how == "odd/even" else (n >= size / 2).astype(int)).rename("part")
    key = box.assign(part=part)[["player_id", "game_id", "part"]]
    shots = shots.merge(key, on=["player_id", "game_id"])
    return [(sums(box[part == k]), shots[shots.part == k]) for k in (0, 1)]


def summary(ranks):
    return {"top1": float((ranks == 0).mean()), "top5": float((ranks < 5).mean()), "mrr": float((1 / (ranks + 1)).mean())}


def archetypes(p, z, names, minutes):
    """Groups of players in the learned space, named by what sets each group apart."""
    best = None
    for k in range(8, 15):
        scores = [silhouette_score(p, KMeans(k, n_init=10, random_state=s).fit_predict(p)) for s in range(3)]
        print(f"{k} archetypes: silhouette {np.mean(scores):.3f}")
        if best is None or np.mean(scores) > best[0]:
            best = (np.mean(scores), k)
    found = KMeans(best[1], n_init=30, random_state=0).fit(p)
    labels = []
    for c in range(best[1]):
        mine = found.labels_ == c
        strength = z[mine].mean(axis=0)
        order = [i for i in strength.argsort()[::-1] if strength[i] > 0.4][:3] or [int(strength.argmax())]
        label = ", ".join(dict.fromkeys(WORDS.get(NAMES[i], FEATURES[NAMES[i]][1].lower().removeprefix("shots: ")) for i in order))
        label = label[0].upper() + label[1:]
        labels.append(label if label not in labels else f"{label} ({c})")
        centre = found.cluster_centers_[c]
        typical = np.where(mine)[0][((p[mine] - centre) ** 2).sum(axis=1).argsort()[:5]]
        print(f"   {label}: {mine.sum()} players, e.g. {', '.join(names[typical])}")
    return found.cluster_centers_, np.array(labels)


WORDS = {
    "mpg": "heavy minutes", "usage": "high usage", "pts36": "scoring", "fga36": "many shots", "fta36": "draws fouls", "ts": "efficient", "two_pct": "efficient inside", "three_pct": "accurate from three", "ft_pct": "good at the line",
    "three_rate": "shoots mostly threes", "ft_rate": "gets to the line", "distance": "shoots from far", "ast36": "passing", "ast_share": "pass first", "tov36": "handles the ball", "tov_rate": "turnover prone", "oreb36": "offensive rebounds",
    "dreb36": "defensive rebounds", "stl36": "steals", "blk36": "shot blocking", "pf36": "physical", "zone:rim": "shots at the rim", "zone:lane": "shots in the lane", "zone:middle": "free-throw-line shots", "zone:baseline": "baseline shots",
    "zone:wing two": "mid-range wings", "zone:corner three": "corner threes", "zone:wing three": "wing threes", "zone:top three": "threes from the top", "zone:deep three": "deep threes", "type:set jump shots": "spot-up shooting",
    "type:cuts": "cutting", "type:drives": "driving", "type:fast breaks": "fast breaks",
}


def main():
    box, shots, folk = load()
    full = sums(box)
    pool = full.index[qualified(full) & (full.gp >= 30)]
    pool = pool[pool.isin(folk.index)]
    positions = np.array([folk.loc[i, "position"].split("-")[0] for i in pool])
    rng = np.random.default_rng(SEED)
    fold = rng.permutation(len(pool)) % FOLDS
    print(f"{len(pool)} players, {len(NAMES)} features")

    prepared = {}
    for how in ("odd/even", "first/second"):
        (sa, ha), (sb, hb) = halves(box, shots, how)
        prepared[how] = {
            "old": standardise(old_vectors(sa).loc[pool].to_numpy(), old_vectors(sb).loc[pool].to_numpy()),
            "new": standardise(features(sa, ha).loc[pool].to_numpy(), features(sb, hb).loc[pool].to_numpy()),
        }

    results = {}
    for how, sets in prepared.items():
        out = {}
        a, b = sets["old"]
        out["12 statistics, Euclidean (before)"] = (identify(a, b), agreement((a + b) / 2, positions))
        unit = [x / np.linalg.norm(x, axis=1, keepdims=True) for x in (a, b)]
        out["12 statistics, cosine"] = (identify(*unit), agreement(unit[0] + unit[1], positions))
        a, b = sets["new"]
        out[f"{len(NAMES)} features, Euclidean"] = (identify(a, b), agreement((a + b) / 2, positions))
        unit = [x / np.linalg.norm(x, axis=1, keepdims=True) for x in (a, b)]
        out[f"{len(NAMES)} features, cosine"] = (identify(*unit), agreement(unit[0] + unit[1], positions))
        for label, columns in (("learned", list(range(len(NAMES)))), ("learned, style only", STYLE)):
            for size in (8, 12, 16, 24):
                ranks, hits = [], []
                for f in range(FOLDS):
                    train, test = fold != f, fold == f
                    ta, tb = (x[train][:, columns] for x in prepared["odd/even"]["new"])
                    w = learn(ta, tb, size)
                    pa, pb = a[:, columns] @ w, b[:, columns] @ w
                    ranks.append(identify(pa, pb, only=test))  # candidates: everyone
                    hits.append(agreement((pa + pb) / 2, positions, only=test))
                out[f"{label}, {size} dimensions"] = (np.concatenate(ranks), np.concatenate(hits))
        results[how] = {k: {**summary(r), "position": float(h.mean())} for k, (r, h) in out.items()}
        print(f"\n{how} games\n| Method | Own half is first | In top 5 | MRR | Same position (5 nearest) |\n|---|---|---|---|---|")
        for k, v in results[how].items():
            print(f"| {k} | {v['top1']:.3f} | {v['top5']:.3f} | {v['mrr']:.3f} | {v['position']:.3f} |")

    # The final model uses every qualified player, scaled on full-season features.
    x = features(full, shots)
    mean, spread = x.loc[pool].mean().to_numpy(), x.loc[pool].std().to_numpy()
    (sa, ha), (sb, hb) = halves(box, shots, "odd/even")
    za, zb = (np.clip((features(s, h).loc[pool].to_numpy() - mean) / spread, -4, 4) for s, h in ((sa, ha), (sb, hb)))
    model = {"mean": mean, "spread": spread}
    full_z = np.clip((x.loc[pool].to_numpy() - mean) / spread, -4, 4)
    for kind, columns, size in (("overall", list(range(len(NAMES))), 24), ("style", STYLE, 24)):
        model[kind] = learn(za[:, columns], zb[:, columns], size)
        p = full_z[:, columns] @ model[kind]
        d = np.sqrt(((p[:, None, :] - p[None, :, :]) ** 2).sum(axis=2))[np.triu_indices(len(p), 1)]
        model[f"{kind}_scale"] = np.median(d) / np.sqrt(np.log(10))
        near = np.sort(np.sqrt(((p[:, None, :] - p[None, :, :]) ** 2).sum(axis=2)), axis=1)[:, 1:11]
        print(f"{kind}: similarity of nearest neighbour, median {np.median(np.exp(-(near[:, 0] / model[f'{kind}_scale']) ** 2)):.2f}, tenth {np.median(np.exp(-(near[:, 9] / model[f'{kind}_scale']) ** 2)):.2f}")
        names = folk.loc[pool, "full_name"].to_numpy()
        for who in ("Nikola Jokić", "Stephen Curry", "Rudy Gobert", "Draymond Green"):
            i = int(np.where(names == who)[0][0])
            di = np.sqrt(((p - p[i]) ** 2).sum(axis=1))
            print("  ", who, [(names[j], round(float(np.exp(-(di[j] / model[f"{kind}_scale"]) ** 2)), 2)) for j in di.argsort()[1:7]])
    model["centres"], model["centre_names"] = archetypes(full_z @ model["overall"], full_z, folk.loc[pool, "full_name"].to_numpy(), full.loc[pool].minutes.to_numpy())
    weights = np.sqrt((model["overall"] ** 2).sum(axis=1))
    print("most important features:", [(NAMES[i], round(float(weights[i]), 2)) for i in weights.argsort()[::-1][:12]])
    MODEL_FILE.parent.mkdir(exist_ok=True)
    np.savez(MODEL_FILE, **model)
    (Path(__file__).resolve().parent.parent / "evaluation" / "results" / "similarity.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
