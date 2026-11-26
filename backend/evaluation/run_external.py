"""Questions written outside this project, run once with the code frozen, without a language model writing answers.

    python evaluation/run_external.py --name external                       the third set, word-matching reader
    python evaluation/run_external.py --set web --reader llm --name web_llm  the fourth set, language-model reader

--set external is evaluation/external_questions.py, --set web is evaluation/web_questions.py.
--reader rules is the word-matching reader; --reader llm lets a language model read each question into a
StatQuery (READER_MODEL; READER_CACHE keeps its answers so a run can be repeated exactly).
The report records the sha256 of the question file, so it can be shown that the set did not change
between being frozen and being run.
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from evaluation.pinning import key_connection, keys  # noqa: E402
from app.services import llm_reader, rag_service  # noqa: E402
from app.services.query_embedding_service import warm_up  # noqa: E402
from evaluation.run_facts import correct, first_named  # noqa: E402

rag_service.OPENROUTER_API_KEY = None  # this measures reading, facts and declining, not prose
NOBODY = re.compile(r"\b(no|none|nobody|no one|not any|nothing)\b", re.I)
SETS = {"external": ("external_questions.py", "E", ["hf", "stathead", "scout"]), "web": ("web_questions.py", "W", ["usc", "statmuse", "quiz"])}


def outcome(provider):
    return {"declined": "declined", "clarify": "asked back", "error": "error"}.get(provider, "answered")


def grade(q, result, expected, names):
    """True/False for graded questions, None for the ones a person has to read."""
    kind = outcome(result["provider"])
    if q["check"] == "judge":
        return None
    if q["check"] == "decline":
        return kind == "declined"
    if kind == "error":
        return False
    if not expected:  # nobody qualifies: the answer must say so
        return kind == "declined" or bool(NOBODY.search(result["answer"][:200]))
    if kind != "answered":
        return False
    if q["check"] == "lead":
        return first_named(result["answer"], names) in expected
    if q["check"] == "nums":
        return any(correct("num", result["answer"], [e], names) for e in expected)
    return correct(q["check"], result["answer"], expected, names)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=list(SETS), default="external")
    parser.add_argument("--reader", choices=["rules", "llm"], default="rules")
    parser.add_argument("--name")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    filename, variable, sources = SETS[args.set]
    name = args.name or f"{args.set}_{args.reader}"
    module = __import__(f"evaluation.{filename[:-3]}", fromlist=[variable])
    questions = getattr(module, variable)
    path = Path(__file__).parent / filename
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.reader == "llm" and not llm_reader.OPENROUTER_API_KEY:
        sys.exit("--reader llm needs OPENROUTER_API_KEY")
    warm_up()
    records = []
    with SessionLocal() as db, key_connection() as kc:  # keys on 2024-25 only (pinning.py)
        names = keys(kc, "select p.full_name from players p join player_season_stats s on s.player_id = p.id") + keys(kc, "select full_name from teams")
        rag_service.answer_question(db, "warm up question about points", None, 6, reader="rules")
        for q in questions:
            expected = keys(kc, q["sql"]) if q["sql"] else []
            started = time.perf_counter()
            try:
                result = rag_service.answer_question(db, q["text"], None, 6, reader=args.reader)
            except Exception as error:  # a crash is a wrong answer
                db.rollback()
                result = {"answer": f"ERROR {type(error).__name__}: {error}", "provider": "error"}
            ms = (time.perf_counter() - started) * 1000
            ok = grade(q, result, expected, names)
            records.append({**{k: q[k] for k in ("id", "source", "ref", "original", "text", "check", "reason")}, "expected": expected, "ok": ok,
                            "outcome": outcome(result["provider"]), "answer": result["answer"], "ms": round(ms),
                            "reader": result.get("reader", ""), "reader_note": result.get("reader_note", ""), "confidence": result.get("confidence"),
                            "signals": result.get("signals", {}), "query": result.get("query"), "understood": result.get("understood", ""),
                            "reader_tokens": result.get("reader_tokens", 0), "reader_ms": result.get("reader_ms", 0)})
            if args.show and ok is False:
                print(f"\nWRONG {q['id']}. {q['text']}\n   expected {q['check']} {expected[:6]}\n   got [{result['provider']}] {result['answer'][:260]}")

    def share(rows):
        return f"{sum(r['ok'] for r in rows)} of {len(rows)} ({sum(r['ok'] for r in rows) / len(rows):.0%})" if rows else "-"

    answerable = [r for r in records if r["check"] not in ("decline", "judge")]
    refusals = [r for r in records if r["check"] == "decline"]
    judged = [r for r in records if r["check"] == "judge"]
    readers = Counter(r["reader"] for r in records)
    lines = [
        f"Question file {filename} sha256: {digest}",
        f"{len(records)} questions, reader {args.reader}{f' ({llm_reader.READER_MODEL}, prompt {llm_reader.PROMPT_VERSION})' if args.reader == 'llm' else ''}, median {statistics.median(r['ms'] for r in records):.0f} ms",
        f"Read by: {', '.join(f'{k} {v}' for k, v in readers.most_common())}" + (f"; reader tokens {sum(r['reader_tokens'] for r in records)}" if args.reader == "llm" else ""),
        "",
        "| Source | Answerable: correct | Should decline: declined | To read: answered |",
        "|---|---|---|---|",
    ]
    for s in sources + ["all"]:
        pick = (lambda rows: [r for r in rows if s == "all" or r["source"] == s])
        read = pick(judged)
        lines.append(f"| {s} | {share(pick(answerable))} | {share(pick(refusals))} | {sum(r['outcome'] == 'answered' for r in read)} of {len(read)} |" if read else f"| {s} | {share(pick(answerable))} | {share(pick(refusals))} | - |")
    lines += ["", "What happened to the questions that should be declined:", "", "| Outcome | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in Counter(r["outcome"] for r in refusals).most_common()]
    lines += ["", "Answerable questions by kind of check:", "", "| Check | Correct |", "|---|---|"]
    by_check = defaultdict(list)
    for r in answerable:
        by_check["nobody qualifies" if not r["expected"] else r["check"]].append(r)
    lines += [f"| {k} | {share(v)} |" for k, v in by_check.items()]
    lines += ["", "Wrong answers:", ""]
    lines += [f"- {r['id']} ({r['source']}, {r['reader']}) {r['text']} | expected {r['expected'][:5] or 'nobody'} | got [{r['outcome']}] {r['answer'][:160]!r}" for r in answerable if not r["ok"]]
    lines += ["", "Answered although it should be declined:", ""]
    lines += [f"- {r['id']} ({r['source']}, {r['reason']}, {r['reader']}) {r['text']} | [{r['outcome']}] {r['answer'][:160]!r}" for r in refusals if not r["ok"]]
    report = "\n".join(lines)
    print("\n" + report)

    out = Path(__file__).parent / "results"
    (out / f"{name}.md").write_text(report + "\n", encoding="utf-8")
    (out / f"{name}.json").write_text(json.dumps({"sha256": digest, "set": args.set, "reader": args.reader, "model": llm_reader.READER_MODEL if args.reader == "llm" else "",
                                                  "prompt": llm_reader.PROMPT_VERSION if args.reader == "llm" else "", "questions": records}, indent=1, ensure_ascii=False), encoding="utf-8")
    if judged:
        reading = [f"# Questions to judge by hand ({name})", ""]
        for r in judged:
            reading += [f"## {r['id']}. {r['text']}", f"Source: {r['source']} ({r['ref']}), original: \"{r['original']}\"", "", f"Outcome: {r['outcome']}", "", r["answer"], ""]
        (out / f"{name}_to_read.md").write_text("\n".join(reading), encoding="utf-8")


if __name__ == "__main__":
    main()
