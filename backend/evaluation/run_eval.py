"""Compare keyword, vector, hybrid and planned retrieval on the question set.

    python evaluation/run_eval.py --split dev      while developing
    python evaluation/run_eval.py --split test     for reporting
    python evaluation/run_eval.py --split dev --show planned    also print what was found
"""

import argparse
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from evaluation.pinning import key_connection, keys  # noqa: E402
from app.services.query_embedding_service import embed_query, warm_up  # noqa: E402
from app.services.retrieval import MODES, retrieve  # noqa: E402
from evaluation.questions import Q, UNANSWERABLE  # noqa: E402

K = 6
METRICS = ["precision", "recall", "mrr", "ndcg", "success"]


def judged(results, item):
    """One entry per distinct entity, in rank order; for "doc" targets the kind must match as well."""
    seen, out = set(), []
    for r in results:
        key = (r["kind"], r["entity"]) if item["target"] == "doc" else r["entity"]
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out[:K]


def score(found, relevant):
    hits = [key in relevant for key in found]
    best = min(K, len(relevant))  # nobody can return more than this
    dcg = sum(1 / math.log2(i + 2) for i, hit in enumerate(hits) if hit)
    ideal = sum(1 / math.log2(i + 2) for i in range(best))
    return {
        "precision": sum(hits) / len(found) if found else 0.0,
        "recall": sum(hits) / best,
        "mrr": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0.0),
        "ndcg": dcg / ideal,
        "success": float(any(hits)),
    }


def run(split, show):
    warm_up()
    records = []
    with SessionLocal() as db, key_connection() as kc:  # keys on 2024-25 only (pinning.py)
        db.execute(text("select 1"))
        for mode in MODES:  # fill the caches so that timings measure retrieval
            retrieve(db, "warm up", None, K, mode)
        for item in (q for q in Q if q["split"] == split):
            truth = kc.execute(text(item["sql"])).scalars().all()
            relevant = {(item["kind"], e) for e in truth} if item["target"] == "doc" else set(truth)
            for mode in MODES:
                embed_query.cache_clear()
                started = time.perf_counter()
                results, plan = retrieve(db, item["text"], None, K, mode)
                ms = (time.perf_counter() - started) * 1000
                db.commit()
                found = judged(results, item)
                records.append({"id": item["id"], "group": item["group"], "question": item["text"], "mode": mode, **score(found, relevant), "ms": round(ms)})
                if show == mode:
                    print(f"\n{item['id']}. {item['text']}  ndcg={records[-1]['ndcg']:.2f}  {plan.intent if plan else ''} {plan.summary() if plan else ''}")
                    for r in results:
                        ok = ((r["kind"], r["entity"]) if item["target"] == "doc" else r["entity"]) in relevant
                        print("   ", "+" if ok else "-", r["kind"], "|", r["title"])
        declined = {q: (lambda p: p is not None and p.intent == "out_of_scope")(retrieve(db, q, None, K)[1]) for q in UNANSWERABLE} if split == "test" else {}
    return records, declined


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0


def table(records):
    lines = ["| Method | P@6 | R@6 | MRR | nDCG@6 | Success@6 | Median ms | p95 ms |", "|---|---|---|---|---|---|---|---|"]
    for mode in MODES:
        rows = [r for r in records if r["mode"] == mode]
        times = sorted(r["ms"] for r in rows)
        lines.append(f"| {mode} | " + " | ".join(f"{mean(rows, m):.3f}" for m in METRICS) + f" | {statistics.median(times):.0f} | {times[math.ceil(0.95 * len(times)) - 1]} |")
    groups = list(dict.fromkeys(r["group"] for r in records))
    lines += ["", "nDCG@6 by question type:", "", "| Type | n | " + " | ".join(MODES) + " |", "|---|---|" + "---|" * len(MODES)]
    for g in groups:
        rows = [r for r in records if r["group"] == g]
        lines.append(f"| {g} | {len(rows) // len(MODES)} | " + " | ".join(f"{mean([r for r in rows if r['mode'] == m], 'ndcg'):.3f}" for m in MODES) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--show", choices=MODES)
    args = parser.parse_args()
    records, declined = run(args.split, args.show)
    report = table(records)
    if declined:
        report += f"\n\nUnanswerable questions declined: {sum(declined.values())} of {len(declined)}\n\n" + "\n".join(f"- {'declined' if ok else 'NOT declined'}: {q}" for q, ok in declined.items())
    print("\n" + report)
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / f"{args.split}.md").write_text(report + "\n", encoding="utf-8")
    (out / f"{args.split}.json").write_text(json.dumps({"questions": records, "declined": declined}, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out / f"{args.split}.csv", "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
