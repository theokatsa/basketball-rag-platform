"""Build or refresh the vector store. Safe to run again: only changed documents are embedded.

    python scripts/build_rag_index.py                 latest season
    python scripts/build_rag_index.py --season 2024-25
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.services.corpus import build_corpus  # noqa: E402
from app.services.query_embedding_service import MODEL_NAME, embed_documents, to_literal  # noqa: E402
from app.services.similarity_service import rows_for_index  # noqa: E402
from app.services.stat_vectors import load_season, qualifies  # noqa: E402

COLUMNS = ["doc_key", "kind", "entity", "season", "title", "content", "search_text", "player_ids", "team_ids", "meta", "content_hash"]
UPDATE = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS[1:])


def build(season: str | None):
    started = time.perf_counter()
    with engine.begin() as conn:
        conn.exec_driver_sql((Path(__file__).parent / "schema_rag.sql").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        vectors = load_season(db, season)
        if vectors is None:
            raise SystemExit(f"No season statistics for {season or 'any season'}.")
        documents = build_corpus(db, vectors)
        styles = rows_for_index(db)
        previous = db.execute(text("select embedding_model from rag_index_info")).scalar()
        stored = dict(db.execute(text("select doc_key, content_hash from rag_documents where season = :s"), {"s": vectors.season}).tuples().all())
    print(f"{vectors.season}: {len(documents)} documents {dict(Counter(d.kind for d in documents))}")

    # Vectors of another model cannot be compared, so a new model means embedding everything.
    reuse = previous == MODEL_NAME
    same = [d for d in documents if reuse and stored.get(d.key) == d.content_hash]
    changed = [d for d in documents if not reuse or stored.get(d.key) != d.content_hash]
    embeddings = embed_documents([d.embedded_text for d in changed]) if changed else []

    def record(d):
        return (d.key, d.kind, d.entity, d.season, d.title, d.content, d.search_text, d.player_ids, d.team_ids, json.dumps(d.meta), d.content_hash)

    gone = sorted(stored.keys() - {d.key for d in documents})
    with engine.begin() as conn:  # one transaction: readers see the old index or the new one
        conn.exec_driver_sql("set local statement_timeout = 0")
        with conn.connection.cursor() as cursor:
            if changed:
                execute_values(
                    cursor,
                    f"insert into rag_documents ({', '.join(COLUMNS)}, embedding) values %s"
                    f" on conflict (doc_key) do update set {UPDATE}, embedding = excluded.embedding, updated_at = now()",
                    [(*record(d), e) for d, e in zip(changed, embeddings)],
                    template="(%s,%s,%s,%s,%s,%s,%s,%s::bigint[],%s::int[],%s::jsonb,%s,%s::vector)", page_size=200,
                )
            if same:  # numbers used for filtering may change while the rounded text does not
                execute_values(
                    cursor, "update rag_documents r set meta = v.meta::jsonb, team_ids = v.team_ids from (values %s) as v(doc_key, meta, team_ids) where r.doc_key = v.doc_key",
                    [(d.key, json.dumps(d.meta), d.team_ids) for d in same], template="(%s,%s,%s::int[])", page_size=500,
                )
            if gone:
                cursor.execute("delete from rag_documents where doc_key = any(%s)", (gone,))
            execute_values(
                cursor, "insert into player_style_vectors (player_id, season, qualified, features, overall, style, archetype) values %s"
                " on conflict (player_id, season) do update set qualified = excluded.qualified, features = excluded.features, overall = excluded.overall, style = excluded.style, archetype = excluded.archetype, updated_at = now()",
                [(p, vectors.season, q, json.dumps(f), o, s, a) for p, q, f, o, s, a in styles], template="(%s,%s,%s,%s::jsonb,%s::vector,%s::vector,%s)", page_size=200,
            )
            cursor.execute("insert into rag_index_info (id, embedding_model) values (1, %s) on conflict (id) do update set embedding_model = excluded.embedding_model, built_at = now()", (MODEL_NAME,))
            execute_values(
                cursor, "insert into player_stat_vectors (player_id, season, qualified, z) values %s"
                " on conflict (player_id, season) do update set qualified = excluded.qualified, z = excluded.z, updated_at = now()",
                [(r["player_id"], vectors.season, qualifies(r), to_literal(vectors.z[i])) for i, r in enumerate(vectors.rows)], template="(%s,%s,%s,%s::vector)", page_size=300,
            )
    print(f"embedded {len(changed)}, unchanged {len(same)}, removed {len(gone)}, stat vectors {len(vectors.rows)}, {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the RAG vector store")
    parser.add_argument("--season", default=None)
    build(parser.parse_args().season)
