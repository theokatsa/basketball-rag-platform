"""Answer keys of the frozen test sets, computed on 2024-25 only, after other seasons were loaded.

The key queries in questions.py, fact_questions.py, external_questions.py and web_questions.py were
written when the database held one season, and some sum a table without naming the season. Those files
are frozen (their sha256 is in the reports), so they are not edited. Instead, keys run on a connection
where temporary views with the same names as the season tables show 2024-25 only. PostgreSQL looks in
the session's temporary schema first, so the unchanged queries read the views.

The names table (players and teams) also comes from this connection, so that "who was named first"
only counts players of that season.
"""

import re
from contextlib import contextmanager

from sqlalchemy import text

from app.db import engine

SEASON = "2024-25"
TABLES = ["player_box_scores", "team_box_scores", "team_period_scores", "player_advanced_stats", "player_season_stats",
          "shot_charts", "player_matchups", "player_pairs", "player_game_logs", "player_stat_vectors", "player_style_vectors", "rag_documents"]


@contextmanager
def key_connection(season: str = SEASON):
    """A connection on which every season table shows one season."""
    if not re.fullmatch(r"\d{4}-\d{2}", season):
        raise ValueError(season)
    with engine.connect() as conn:
        for table in TABLES:
            conn.execute(text(f"create temporary view {table} as select * from public.{table} where season = '{season}'"))
        conn.commit()  # created and kept for the session, so a failed key query cannot remove them
        yield conn


def keys(conn, sql: str) -> list[str]:
    try:
        return [str(v) for v in conn.execute(text(sql)).scalars()]
    except Exception:
        conn.rollback()  # the temporary views stay: they belong to the session, not the transaction
        raise
