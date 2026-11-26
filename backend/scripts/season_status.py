"""Rows per season in every table that has seasons, the local Parquet seasons, and the database size.

    python scripts/season_status.py
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from db_utils import engine  # noqa: E402

TABLES = ["player_season_stats", "player_advanced_stats", "player_box_scores", "team_box_scores", "games", "player_game_logs", "team_period_scores",
          "player_matchups", "player_pairs", "shot_charts", "rag_documents", "player_stat_vectors", "player_style_vectors"]
LOCAL = Path(__file__).resolve().parents[2] / "data"

with engine.connect() as conn:
    counts = {t: dict(conn.execute(text(f"select season, count(*) from {t} group by 1")).all()) for t in TABLES}
    size = conn.execute(text("select pg_size_pretty(pg_database_size(current_database()))")).scalar()
seasons = sorted({s for c in counts.values() for s in c})
print(f"Supabase: {size} of the free plan's 500 MB\n")
print(f"{'table':24}" + "".join(f"{s:>10}" for s in seasons))
for t in TABLES:
    print(f"{t:24}" + "".join(f"{counts[t].get(s, 0):>10,}" for s in seasons))
if LOCAL.exists():
    for folder in sorted(p for p in LOCAL.iterdir() if p.is_dir()):
        files = sorted(folder.glob("*.parquet"))
        print(f"\nOn this computer, {folder.name} ({sum(f.stat().st_size for f in files) / 1e6:.1f} MB):")
        for f in files:
            print(f"  {f.stem:24}{len(pd.read_parquet(f, columns=[])):>10,}")
