import argparse
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import engine
from embedding_utils import build_embedding

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.stat_vectors import describe, load_season  # noqa: E402

UPSERT = text(
    """
    insert into player_embeddings (player_id, season, embedding, source_text)
    values (:player_id, :season, cast(:embedding as vector), :source_text)
    on conflict (player_id, season)
    do update set embedding = excluded.embedding, source_text = excluded.source_text
    """
)


def ingest_player_embeddings(season: str | None = None, only_changed: bool = False):
    """Embed one description per player and statistical season.

    The season key matches player_season_stats ("2024-25"), so retrieval can join on it.
    """
    with engine.begin() as conn:
        conn.execute(text("set local statement_timeout = 0"))
        seasons = [season] if season else list(
            conn.execute(text("select distinct season from player_season_stats order by 1")).scalars()
        )
        for current in seasons:
            vectors = load_season(conn, current)
            if vectors is None:
                print(f"No season statistics for {current}.")
                continue
            existing = dict(
                conn.execute(
                    text("select player_id, source_text from player_embeddings where season = :s"),
                    {"s": current},
                ).tuples().all()
            )
            processed = 0
            for player_id in vectors.index:
                source_text = describe(vectors, player_id)
                if only_changed and existing.get(player_id) == source_text:
                    continue
                conn.execute(
                    UPSERT,
                    {
                        "player_id": player_id,
                        "season": current,
                        "embedding": build_embedding(source_text),
                        "source_text": source_text,
                    },
                )
                processed += 1
            print(f"Upserted {processed} player embeddings for {current}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed player season descriptions")
    parser.add_argument("--season", default=None, help="One season, e.g. 2024-25 (default: all)")
    parser.add_argument("--only-changed", action="store_true", help="Skip rows that are already up to date")
    args = parser.parse_args()
    ingest_player_embeddings(args.season, args.only_changed)
