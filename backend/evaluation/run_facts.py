"""Answer accuracy on the factual questions, without a language model.

    python evaluation/run_facts.py --split dev --show
    python evaluation/run_facts.py --split test --name test_final
"""

import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.services import rag_service  # noqa: E402
from app.services.query_embedding_service import warm_up  # noqa: E402
from app.services.text_utils import normalize_name  # noqa: E402
from evaluation.fact_questions import F  # noqa: E402

rag_service.OPENROUTER_API_KEY = None  # this measures facts, not prose


def first_named(answer, names):
    found = [(m.start(), -len(n), n) for n in names if (m := re.search(rf"(?<!\w){re.escape(normalize_name(n))}(?!\w)", normalize_name(answer)))]
    return min(found)[2] if found else None


def correct(check, answer, expected, names):
    if check == "num":
        want = float(expected[0])
        whole = want == int(want) and "." not in str(expected[0])
        for n in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", re.sub(r"\b\d{4}[-–]\d{2}\b", " ", answer)):
            if abs(abs(float(n.replace(",", ""))) - abs(want)) <= (0 if whole else 0.06):
                return True
        return False
    if check == "lead":
        return first_named(answer, names) == expected[0]
    plain = normalize_name(answer).replace("–", "-")
    return all(normalize_name(str(e)) in plain for e in expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--name")
    args = parser.parse_args()
    warm_up()
    records = []
    with SessionLocal() as db:
        names = list(db.execute(text("select p.full_name from players p join player_season_stats s on s.player_id = p.id")).scalars()) + list(db.execute(text("select full_name from teams")).scalars())
        rag_service.answer_question(db, "warm up question about points", None, 6)
        for q in (q for q in F if q["split"] == args.split):
            expected = [str(v) for v in db.execute(text(q["sql"])).scalars()]
            started = time.perf_counter()
            try:
                result = rag_service.answer_question(db, q["text"], None, 6)
            except Exception as error:  # a crash is a wrong answer
                db.rollback()
                result = {"answer": f"ERROR {type(error).__name__}: {error}", "provider": "error"}
            ms = (time.perf_counter() - started) * 1000
            ok = correct(q["check"], result["answer"], expected, names)
            records.append({"id": q["id"], "page": q["page"], "text": q["text"], "ok": ok, "expected": expected, "answer": result["answer"], "provider": result["provider"], "ms": round(ms)})
            if args.show and not ok:
                print(f"\nWRONG {q['id']}. {q['text']}\n   expected {q['check']} {expected}\n   got [{result['provider']}] {result['answer'][:260]}")
    pages = defaultdict(list)
    for r in records:
        pages[r["page"]].append(r["ok"])
    lines = [f"Accuracy: {sum(r['ok'] for r in records)} of {len(records)} ({sum(r['ok'] for r in records) / len(records):.1%}), median {statistics.median(r['ms'] for r in records):.0f} ms", "", "| Topic | Correct | Asked |", "|---|---|---|"]
    lines += [f"| {p} | {sum(v)} | {len(v)} |" for p, v in pages.items()]
    print("\n" + "\n".join(lines))
    if args.name:
        out = Path(__file__).parent / "results"
        (out / f"facts_{args.name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (out / f"facts_{args.name}.json").write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
