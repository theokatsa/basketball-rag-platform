import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from embedding_utils import build_embedding

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def ingest_player_embeddings(season: str | None = None):
    select_sql = text(
        """
        select pp.player_id,
               pp.season,
               pp.description,
               p.full_name
        from player_profiles pp
        join players p on p.id = pp.player_id
                where (:season is null or pp.season = :season)
                    and pp.description is not null
        order by p.full_name
        """
    )

    upsert_sql = text(
        """
        insert into player_embeddings (
            player_id,
            season,
            embedding,
            source_text
        )
        values (
            :player_id,
            :season,
            cast(:embedding as vector),
            :source_text
        )
        on conflict (player_id, season)
        do update set
            embedding = excluded.embedding,
            source_text = excluded.source_text
        """
    )

    with engine.begin() as conn:
        conn.execute(text("set local statement_timeout = 0"))
        rows = conn.execute(select_sql, {"season": season}).mappings().all()

        processed = 0
        for row in rows:
            source_text = row["description"]
            embedding = build_embedding(source_text)

            conn.execute(
                upsert_sql,
                {
                    "player_id": row["player_id"],
                    "season": row["season"],
                    "embedding": embedding,
                    "source_text": source_text,
                },
            )
            processed += 1

    season_label = season if season is not None else "all seasons"
    print(f"Upserted {processed} player embeddings for {season_label}.")


if __name__ == "__main__":
    ingest_player_embeddings()