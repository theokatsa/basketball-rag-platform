"""Train the paraphrase router and report how it does on phrases it never saw.

    python training/train_router.py

Uses the embedding model named by EMBEDDING_MODEL. The regularisation is chosen by
cross-validation on the training phrases; the held-out quarter is only measured. The router is
right about one time in three with its first guess and two in three within three guesses, so it is used to ask
back ("did you mean...?") and never to answer. The stored classifier is fitted on all phrases.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from app.services.paraphrase_router import FILE  # noqa: E402
from app.services.query_embedding_service import MODEL_NAME, encode  # noqa: E402
from training.phrases import NONE, PHRASES, split  # noqa: E402


def within(p, classes, truth, k):
    order = p.argsort(axis=1)[:, ::-1][:, :k]
    related = truth != NONE
    return float(np.mean([t in classes[r] for r, t in zip(order[related], truth[related])]))


def classifier(c):
    return LogisticRegression(C=c, max_iter=3000, class_weight="balanced")


def main():
    train, test = split()
    x, y = encode([p for p, _ in train]), np.array([c for _, c in train])
    xt, yt = encode([p for p, _ in test]), np.array([c for _, c in test])
    folds = StratifiedKFold(4, shuffle=True, random_state=0)
    scores = {c: within(cross_val_predict(classifier(c), x, y, cv=folds, method="predict_proba"), np.unique(y), y, 3) for c in (1, 3, 10, 30, 100)}
    best = max(scores, key=scores.get)
    model = classifier(best).fit(x, y)
    p = model.predict_proba(xt)
    held = {f"top{k}": within(p, model.classes_, yt, k) for k in (1, 2, 3, 4)}
    unrelated = yt == NONE
    held["unrelated recognised"] = float((model.classes_[p[unrelated].argmax(axis=1)] == NONE).mean())
    print(f"{MODEL_NAME}: C={best}, held-out phrases ({int((~unrelated).sum())} related, {int(unrelated.sum())} unrelated):", json.dumps({k: round(v, 3) for k, v in held.items()}))
    final = classifier(best).fit(np.vstack([x, xt]), np.concatenate([y, yt]))
    FILE.parent.mkdir(exist_ok=True)
    np.savez(FILE, weights=final.coef_, bias=final.intercept_, info=json.dumps({"model": MODEL_NAME, "words": [PHRASES[k][0] for k in final.classes_]}))
    out = Path(__file__).resolve().parent.parent / "evaluation" / "results" / "router.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    results[MODEL_NAME] = {"C": best, "cross-validated top3": scores[best], "held_out": held}
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
