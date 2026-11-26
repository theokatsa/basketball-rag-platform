"""The "G" of RAG: what the language model does when it writes the answer from the sources.

    python evaluation/run_generation.py --set web --reader llm --name generation_web

Runs a question set (see run_external.py) with the writer switched on and measures, for every answer
that was written by the model:
  grounded        every number appears in a source (rounding allowed)
  right owner     no number the sources give to another player or team (grounding.misattributed)
  citations       the answer cites at least one source and no missing one
  kept right      the written answer passes the same check as the calculated sentence it was written from
                  (the first source); "broke" counts written answers that lost a right answer
  latency, tokens and cost (prices read from OpenRouter for the model used)
and writes results/<name>_to_rate.md: a sample of answers with their sources for a person to score
(faithful / complete / clear, 0-2 each). Needs OPENROUTER_API_KEY with credit.
"""

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_MODEL  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from evaluation.pinning import key_connection, keys  # noqa: E402
from app.services import rag_service  # noqa: E402
from app.services.query_embedding_service import warm_up  # noqa: E402
from evaluation.run_external import SETS, grade  # noqa: E402

SAMPLE = 40


def prices(model: str) -> tuple[float, float]:
    """Dollars per token (prompt, completion), or zeros when OpenRouter does not say."""
    try:
        for m in httpx.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]:
            if m["id"] == model:
                return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])
    except Exception:  # noqa: BLE001 - the cost is then reported as unknown
        pass
    return 0.0, 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=list(SETS), default="web")
    parser.add_argument("--reader", choices=["rules", "llm"], default="llm")
    parser.add_argument("--name")
    args = parser.parse_args()
    if not OPENROUTER_API_KEY:
        sys.exit("The writer needs OPENROUTER_API_KEY.")
    filename, variable, _ = SETS[args.set]
    questions = [q for q in getattr(__import__(f"evaluation.{filename[:-3]}", fromlist=[variable]), variable) if q["check"] not in ("decline", "judge")]
    name = args.name or f"generation_{args.set}"
    warm_up()
    records = []
    with SessionLocal() as db, key_connection() as kc:  # keys on 2024-25 only (pinning.py)
        names = keys(kc, "select p.full_name from players p join player_season_stats s on s.player_id = p.id") + keys(kc, "select full_name from teams")
        for q in questions:
            expected = keys(kc, q["sql"]) if q["sql"] else []
            started = time.perf_counter()
            try:
                result = rag_service.answer_question(db, q["text"], None, 6, reader=args.reader)
            except Exception as error:  # noqa: BLE001
                db.rollback()
                result = {"answer": f"ERROR {error}", "provider": "error", "sources": []}
            written = result.get("provider") not in ("calculated", "extractive", "declined", "clarify", "error")
            first = result.get("sources", [{}])[0].get("source_text", "") if result.get("sources") else ""
            checks = result.get("checks") or {}
            records.append({
                "id": q["id"], "text": q["text"], "written": written, "model": result.get("model", ""), "answer": result.get("answer", ""),
                "ok": grade(q, result, expected, names), "template_ok": grade(q, {"provider": "calculated", "answer": first}, expected, names) if first and result.get("intent") == "calculated" else None,
                "grounded": not checks.get("unsupported_numbers"), "right_owner": not checks.get("misattributed"), "cites": bool(checks.get("cited")) and not checks.get("invalid_citations"),
                "checks": checks, "generation_ms": result.get("generation_ms", 0), "tokens": result.get("generation_tokens", 0), "ms": round((time.perf_counter() - started) * 1000),
                "sources": [{"ref": s["ref"], "title": s["title"], "text": s["source_text"][:600]} for s in result.get("sources", [])],
            })
    out = [r for r in records if r["written"]]
    share = lambda key: f"{sum(r[key] for r in out)} of {len(out)} ({sum(r[key] for r in out) / len(out):.0%})" if out else "-"  # noqa: E731
    compared = [r for r in out if r["template_ok"] is not None]
    broke = sum(1 for r in compared if r["template_ok"] and not r["ok"])
    fixed = sum(1 for r in compared if not r["template_ok"] and r["ok"])
    model = out[0]["model"] if out else OPENROUTER_MODEL
    prompt_price, completion_price = prices(model)
    tokens = sum(r["tokens"] for r in out)
    lines = [
        f"{len(records)} answerable questions of the {args.set} set, reader {args.reader}, writer {model}: {len(out)} answers written by the model.",
        "",
        "| Measure | Result |", "|---|---|",
        f"| Every number in a source | {share('grounded')} |",
        f"| No number given to the wrong player or team | {share('right_owner')} |",
        f"| Cites sources, none missing | {share('cites')} |",
        f"| Right answer (as graded) | {share('ok')} |",
        f"| Calculated sentence right, written answer wrong (broke) | {broke} of {len(compared)} |",
        f"| Calculated sentence wrong, written answer right | {fixed} of {len(compared)} |",
        f"| Median writing time | {statistics.median(r['generation_ms'] for r in out) / 1000:.1f} s |" if out else "| Median writing time | - |",
        f"| Tokens (prompt + answer) | {tokens} in total, {tokens / max(1, len(out)):.0f} per answer |",
        f"| Cost (rough: all tokens at the prompt price) | ${tokens * prompt_price:.4f} in total |" if prompt_price else "| Cost | price unknown |",
    ]
    report = "\n".join(lines)
    print(report)
    folder = Path(__file__).parent / "results"
    (folder / f"{name}.md").write_text(report + "\n", encoding="utf-8")
    (folder / f"{name}.json").write_text(json.dumps({"set": args.set, "reader": args.reader, "model": model, "records": records}, indent=1, ensure_ascii=False), encoding="utf-8")
    sample = random.Random(7).sample(out, min(SAMPLE, len(out)))
    sheet = [f"# Written answers to score by hand ({name})", "", "For each: faithful to the sources (0-2), complete for the question (0-2), clear (0-2).", ""]
    for r in sample:
        sheet += [f"## {r['id']}. {r['text']}", "", "Sources:", *[f"- [{s['ref']}] {s['title']}: {s['text']}" for s in r["sources"]], "", f"Answer: {r['answer']}", "",
                  "Faithful: _ Complete: _ Clear: _", ""]
    (folder / f"{name}_to_rate.md").write_text("\n".join(sheet), encoding="utf-8")


if __name__ == "__main__":
    main()
