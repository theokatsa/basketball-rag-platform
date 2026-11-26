"""Questions people asked on the site, with their verdicts, as the start of a new test set.

    python evaluation/export_asked.py --source study            results/asked_study.md and .json
    python evaluation/export_asked.py --source study --since 2026-12-01

Nothing is graded here. Each question still needs an answer key written by SQL on the raw tables,
like evaluation/external_questions.py, before the system is run on it. The verdicts ("was this right?")
are a second, rougher measure: what the people themselves thought.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="study")
    parser.add_argument("--since", default="2000-01-01")
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = [dict(r) for r in db.execute(text("""
            select a.id::text as id, a.visitor::text as visitor, a.question, a.previous, a.understood, a.reader, a.provider, a.intent, a.answer, a.asked_at::text as asked_at,
                   f.helpful, f.reason, f.comment
            from ask_log a left join answer_feedback f on f.ask_id = a.id
            where a.source = :source and a.asked_at >= cast(:since as date)
            order by a.asked_at"""), {"source": args.source, "since": args.since}).mappings()]
    people = len({r["visitor"] for r in rows if r["visitor"]})
    judged = [r for r in rows if r["helpful"] is not None]
    lines = [
        f"# Questions asked on the site (source '{args.source}', since {args.since})", "",
        f"{len(rows)} questions from {people} browsers; {len(judged)} answers judged by the person who asked,"
        f" {sum(r['helpful'] for r in judged)} of them as right.", "",
        "| Outcome | Count |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in Counter(r["provider"] for r in rows).most_common()], "",
        "| Reason given for a wrong answer | Count |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in Counter(r["reason"] or "none given" for r in judged if not r["helpful"]).most_common()], "",
        "## Questions", "",
    ]
    for r in rows:
        verdict = "" if r["helpful"] is None else " | judged right" if r["helpful"] else f" | judged wrong: {r['reason'] or '-'}{' - ' + r['comment'] if r['comment'] else ''}"
        lines.append(f"- {r['question']} [{r['provider']}]{verdict}")
    out = Path(__file__).parent / "results"
    (out / f"asked_{args.source}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / f"asked_{args.source}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
