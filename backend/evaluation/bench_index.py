"""Exact scan against the HNSW index on rag_documents: recall@10 and latency inside the server."""

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.services.query_embedding_service import embed_query  # noqa: E402
from evaluation.questions import Q  # noqa: E402

SQL = "select id from rag_documents order by embedding <=> cast(:e as vector) limit 10"


def run(db, settings, embedding):
    for s in settings:
        db.execute(text(f"set local {s}"))
    ids = list(db.execute(text(SQL), {"e": embedding}).scalars())
    plan = db.execute(text("explain (analyze, format json) " + SQL), {"e": embedding}).scalar()
    plan = plan if isinstance(plan, list) else json.loads(plan)
    db.rollback()
    return ids, plan[0]["Execution Time"], "rag_documents_hnsw" in json.dumps(plan)


with SessionLocal() as db:
    total = db.execute(text("select count(*) from rag_documents")).scalar()
    embeddings = [embed_query(q["text"]) for q in Q]
    for e in embeddings[:3]:
        run(db, [], e)  # warm the buffers
    exact = [run(db, ["enable_indexscan = off"], e) for e in embeddings]
    print(f"{total} vectors, {len(Q)} queries")
    print(f"| Search | Recall@10 | Median ms | Index used |\n|---|---|---|---|\n| exact scan | 1.000 | {statistics.median(x[1] for x in exact):.2f} | {any(x[2] for x in exact)} |")
    for ef in (10, 40, 100, 200):
        found = [run(db, [f"hnsw.ef_search = {ef}", "enable_seqscan = off"], e) for e in embeddings]
        recall = sum(len(set(a[0]) & set(b[0])) / 10 for a, b in zip(found, exact)) / len(Q)
        print(f"| HNSW ef_search={ef} | {recall:.3f} | {statistics.median(x[1] for x in found):.2f} | {all(x[2] for x in found)} |")
