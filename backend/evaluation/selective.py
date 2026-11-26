"""When should the system answer? Risk against coverage, from the results of run_external.py.

    python evaluation/selective.py results/external_rules.json results/web_llm.json
    python evaluation/selective.py --fit results/external_llm.json --test results/web_llm.json

Every graded question counts (the "judge" ones are left out). A declined or asked-back question is not
answered; an answered one is right or wrong, and answering a question that should be declined is wrong.
Lowering the confidence needed to answer raises coverage (the share answered) and usually risk (the
share of answers that are wrong). AURC is the area under that curve: lower is better. A system that
answers everything at once has a single point.

--fit learns the weight of each signal (logistic regression) on a set that has already been seen, and
reports it on a test set next to the hand-set confidence of rag_service.confidence.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")


def load(path: str) -> list[dict]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["questions"]
    return [r for r in rows if r["ok"] is not None]


def curve(rows: list[dict], scores: list[float]) -> tuple[list[tuple[float, float, float, int, int]], float]:
    """(threshold, coverage, risk, right, wrong) at every distinct confidence, and the AURC."""
    n = len(rows)
    answered = [(s, r["ok"]) for r, s in zip(rows, scores) if r["outcome"] == "answered"]
    points, area, last_cover = [], 0.0, 0.0
    for threshold in sorted({s for s, _ in answered}, reverse=True):
        kept = [ok for s, ok in answered if s >= threshold]
        right, wrong = sum(kept), len(kept) - sum(kept)
        cover, risk = len(kept) / n, wrong / len(kept)
        area += risk * (cover - last_cover)
        last_cover = cover
        points.append((threshold, cover, risk, right, wrong))
    return points, area


def table(name: str, rows: list[dict], scores: list[float]) -> str:
    points, area = curve(rows, scores)
    declined = sum(r["outcome"] != "answered" for r in rows)
    should = sum(r["check"] == "decline" for r in rows)
    lines = [f"### {name}", "", f"{len(rows)} graded questions, {should} of them should be declined; the system declined or asked back {declined}. AURC {area:.3f}.", "",
             "| Answer when confidence is at least | Coverage | Risk (wrong share) | Right | Wrong |", "|---|---|---|---|---|"]
    lines += [f"| {t:.2f} | {c:.0%} | {k:.0%} | {r} | {w} |" for t, c, k, r, w in points]
    return "\n".join(lines)


SIGNALS = ["llm_calculated", "agree_yes", "agree_no", "rules_calculated", "fallback", "retrieved", "conditions"]


def features(r: dict) -> list[float]:
    s = r.get("signals") or {}
    llm = s.get("reader") in ("llm", "edited") and s.get("calculated")
    return [float(bool(llm)), float(s.get("agree") is True), float(s.get("agree") is False), float(s.get("reader") == "rules" and bool(s.get("calculated"))),
            float(bool(s.get("fallback"))), float(not s.get("calculated")), float(min(s.get("conditions") or 0, 4))]


def fit(train: list[dict]):
    from sklearn.linear_model import LogisticRegression

    answered = [r for r in train if r["outcome"] == "answered"]
    x = np.array([features(r) for r in answered])
    y = np.array([bool(r["ok"]) for r in answered])
    if len(set(y)) < 2:
        sys.exit("The training set needs right and wrong answers.")
    return LogisticRegression(C=1.0, max_iter=1000).fit(x, y)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="*")
    parser.add_argument("--fit")
    parser.add_argument("--test")
    args = parser.parse_args()
    for path in args.results:
        rows = load(path)
        print(table(Path(path).stem + " (confidence of rag_service)", rows, [r.get("confidence") or 0.0 for r in rows]) + "\n")
    if args.fit and args.test:
        model = fit(load(args.fit))
        rows = load(args.test)
        learned = model.predict_proba(np.array([features(r) for r in rows]))[:, 1]
        print(table(Path(args.test).stem + " (hand-set confidence)", rows, [r.get("confidence") or 0.0 for r in rows]) + "\n")
        print(table(Path(args.test).stem + f" (weights learned on {Path(args.fit).stem})", rows, list(learned)) + "\n")
        print("Learned weights: " + ", ".join(f"{name} {w:+.2f}" for name, w in zip(SIGNALS, model.coef_[0])) + f", intercept {model.intercept_[0]:+.2f}")


if __name__ == "__main__":
    main()
