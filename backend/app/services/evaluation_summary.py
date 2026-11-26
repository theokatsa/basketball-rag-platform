"""The headline results of the evaluation, read from backend/evaluation/results, for the How it works page.

Nothing is computed here that the evaluation scripts did not already store; numbers on the page and in
docs/vector-and-rag.md come from the same files.
"""

import json
from pathlib import Path
from statistics import mean

RESULTS = Path(__file__).resolve().parents[2] / "evaluation" / "results"
OUTSIDE = [  # (file, label), the first file found of each group is used
    (["external_rules"], "Third set (web-sourced, seen), word-matching reader"),
    (["external_llm"], "Third set (web-sourced, seen), language-model reader"),
    (["web_rules"], "Fourth set (web, frozen), word-matching reader"),
    (["web_llm"], "Fourth set (web, frozen), language-model reader"),
]
SIMILARITY = [("12 statistics, Euclidean (before)", "12 averages"), ("42 features, Euclidean", "42 features"), ("learned, 24 dimensions", "learned (used)"), ("learned, style only, 24 dimensions", "learned, style only (used)")]


def _read(name: str):
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _outside(data: dict) -> dict:
    rows = data["questions"] if isinstance(data, dict) else data
    answerable = [r for r in rows if r["check"] not in ("decline", "judge")]
    refusals = [r for r in rows if r["check"] == "decline"]
    return {
        "answerable": len(answerable), "correct": sum(bool(r["ok"]) for r in answerable),
        "should_decline": len(refusals), "declined": sum(bool(r["ok"]) for r in refusals),
        "model": data.get("model", "") if isinstance(data, dict) else "",
    }


def summary() -> dict:
    out: dict = {"retrieval": [], "facts": None, "outside": [], "similarity": []}
    if test := _read("test"):
        modes: dict[str, list[float]] = {}
        for r in test["questions"]:
            modes.setdefault(r["mode"], []).append(r["ndcg"])
        out["retrieval"] = [{"method": m, "ndcg": round(mean(v), 3), "questions": len(v)} for m, v in modes.items()]
    if facts := _read("facts_test_final"):
        out["facts"] = {"correct": sum(bool(r["ok"]) for r in facts), "total": len(facts)}
    for names, label in OUTSIDE:
        for name in names:
            if data := _read(name):
                out["outside"].append({"label": label, "file": name, **_outside(data)})
                break
    if similar := _read("similarity"):
        for key, label in SIMILARITY:
            if key in similar.get("odd/even", {}):
                out["similarity"].append({"method": label, "own_half_first": round(similar["odd/even"][key]["top1"], 3),
                                          "later_half_first": round(similar.get("first/second", {}).get(key, {}).get("top1", 0), 3)})
    return out
