"""Questions asked on the site, and what people said about the answers and the similar-player lists.

The questions are the start of a test set written by other people (docs/vector-and-rag.md, part 15):
an answer key is added later by hand, so nothing here grades anything.
No row names a person. Tables: scripts/schema_feedback.sql.
"""

import json
import logging
import random
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from sqlalchemy import text

from app.core.config import ASK_LOG_SOURCE
from app.db import SessionLocal

SCHEMA = Path(__file__).resolve().parents[2] / "scripts" / "schema_feedback.sql"
REASONS = ("wrong_stat", "wrong_player", "should_decline", "wrong_number", "other")
LIMIT, WINDOW = 120, 600  # posts per client per 10 minutes
_posts: dict[str, deque] = defaultdict(deque)
log = logging.getLogger(__name__)


def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA.read_text(encoding="utf-8"))


def allowed(client: str) -> bool:
    """A loose limit, so one script cannot fill the tables."""
    now = time.monotonic()
    recent = _posts[client]
    while recent and now - recent[0] > WINDOW:
        recent.popleft()
    if len(recent) >= LIMIT:
        return False
    recent.append(now)
    return True


def new_id() -> str:
    return str(uuid.uuid4())


def log_question(ask_id: str, visitor: str | None, question: str, previous: str | None, result: dict) -> None:
    """Runs after the answer was sent, with its own connection; a failure only loses this row."""
    try:
        with SessionLocal() as db:
            db.execute(
                text("""insert into ask_log (id, source, visitor, question, previous, understood, reader, provider, intent, plan, answer, ms)
                        values (cast(:id as uuid), :source, cast(:visitor as uuid), :question, :previous, :understood, :reader, :provider, :intent, cast(:plan as jsonb), :answer, :ms)"""),
                {
                    "id": ask_id, "source": ASK_LOG_SOURCE, "visitor": visitor, "question": question, "previous": previous,
                    "understood": result.get("understood", ""), "reader": result.get("reader", "rules"), "provider": result.get("provider", ""),
                    "intent": result.get("intent", ""), "plan": json.dumps(result.get("plan", [])), "answer": result.get("answer", "")[:4000],
                    "ms": int(result.get("retrieval_ms", 0)) + int(result.get("generation_ms", 0)),
                },
            )
            db.commit()
    except Exception as error:  # noqa: BLE001 - logging must never break answering
        log.warning("question not logged: %s", error)


def answer_feedback(db, ask_id: str, helpful: bool, reason: str | None, comment: str | None) -> bool:
    """False when the answer is not in the log (not logged, or logged elsewhere)."""
    row = db.execute(
        text("""insert into answer_feedback (ask_id, helpful, reason, comment)
                select id, :helpful, :reason, :comment from ask_log where id = cast(:id as uuid)
                on conflict (ask_id) do update set helpful = excluded.helpful, reason = excluded.reason, comment = excluded.comment, created_at = now()
                returning ask_id"""),
        {"id": ask_id, "helpful": helpful, "reason": None if helpful else reason, "comment": (comment or "").strip()[:600] or None},
    ).first()
    db.commit()
    return row is not None


# ------------------------------------------------------------------ the blind test of similar players

METHODS = ("overall", "production")  # learned from 42 features, against the twelve averages used before
LIST_LENGTH, TRIAL_MINUTES = 5, 60
_trials: dict[str, dict] = {}  # kept here, not sent to the page, so the page cannot know which list is which


def next_trial(db, visitor: str) -> dict | None:
    """A regular player this browser has not judged yet, with the two lists in random order."""
    from app.services import league_data
    from app.services.embedding_service import get_similar_players

    now = time.monotonic()
    for key in [k for k, t in _trials.items() if now - t["at"] > TRIAL_MINUTES * 60]:
        _trials.pop(key, None)
    people = league_data.people(db)
    regulars = people[(people["gp"] >= 40) & (people["mpg"] >= 20)]["player_id"].tolist()
    done = set(db.execute(text("select player_id from similarity_judgments where visitor = cast(:v as uuid)"), {"v": visitor}).scalars())
    left_over = [p for p in regulars if p not in done]
    chance = random.SystemRandom()
    for player in chance.sample(left_over, min(8, len(left_over))):
        lists = {m: [int(r["player_id"]) for r in get_similar_players(db, int(player), None, LIST_LENGTH, m, "any")] for m in METHODS}
        if len(lists[METHODS[0]]) < LIST_LENGTH or lists[METHODS[0]] == lists[METHODS[1]]:
            continue  # identical lists teach nothing
        order = list(METHODS)
        chance.shuffle(order)
        trial = new_id()
        _trials[trial] = {"at": now, "visitor": visitor, "player": int(player), "left": order[0], "right": order[1], "left_ids": lists[order[0]], "right_ids": lists[order[1]]}
        return {"trial": trial, "player_id": int(player), "left": lists[order[0]], "right": lists[order[1]], "judged": len(done)}
    return None


def save_judgment(db, trial: str, visitor: str, choice: str) -> bool:
    t = _trials.pop(trial, None)
    if t is None or t["visitor"] != visitor:
        return False
    db.execute(
        text("""insert into similarity_judgments (source, visitor, player_id, left_method, right_method, left_ids, right_ids, choice)
                values (:source, cast(:visitor as uuid), :player, :left, :right, :left_ids, :right_ids, :choice)"""),
        {"source": ASK_LOG_SOURCE, "visitor": visitor, "player": t["player"], "left": t["left"], "right": t["right"], "left_ids": t["left_ids"], "right_ids": t["right_ids"], "choice": choice},
    )
    db.commit()
    return True


def similar_feedback(db, visitor: str, player_id: int, other_id: int, kind: str, variant: str, rank: int, similarity: float | None, good: bool) -> None:
    db.execute(
        text("""insert into similar_feedback (source, visitor, player_id, other_id, kind, variant, rank, similarity, good)
                values (:source, cast(:visitor as uuid), :player, :other, :kind, :variant, :rank, :similarity, :good)
                on conflict (visitor, player_id, other_id, kind, variant) do update set good = excluded.good, rank = excluded.rank, similarity = excluded.similarity, created_at = now()"""),
        {"source": ASK_LOG_SOURCE, "visitor": visitor, "player": player_id, "other": other_id, "kind": kind, "variant": variant, "rank": rank, "similarity": similarity, "good": good},
    )
    db.commit()
