import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import engine


def fetch_player_profiles(season: str | None = None):
    sql = text(
        """
        select pp.id,
               pp.player_id,
               p.nba_player_id,
               p.full_name,
               pp.season,
               pp.team_id,
               t.full_name as team_name,
               pp.position,
               pp.age,
               pp.height,
               pp.weight,
               pp.description,
               pp.created_at
        from player_profiles pp
        join players p on p.id = pp.player_id
        left join teams t on t.id = pp.team_id
        where (:season is null or pp.season = :season)
        order by p.full_name
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(sql, {"season": season}).mappings().all()

    return [dict(row) for row in rows]


def write_json(rows, output_path: Path | None):
    payload = json.dumps(rows, indent=2, default=str)
    if output_path:
        output_path.write_text(payload, encoding="utf-8")
        print(f"Wrote {len(rows)} profiles to {output_path}")
    else:
        print(payload)


def write_csv(rows, output_path: Path | None):
    if not rows:
        print("No profiles found.")
        return

    fieldnames = list(rows[0].keys())
    if output_path:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} profiles to {output_path}")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows, limit: int):
    if not rows:
        print("No profiles found.")
        return

    for row in rows[:limit]:
        print(f"{row['full_name']} | season={row['season']} | team={row['team_name']} | position={row['position']}")
        print(row["description"])
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(description="Fetch player profiles from the database")
    parser.add_argument("--season", default=None, help="Filter by season, e.g. 2024-25")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table")
    parser.add_argument("--output", default=None, help="Optional output file path")
    parser.add_argument("--limit", type=int, default=20, help="How many profiles to print in table mode")
    args = parser.parse_args()

    rows = fetch_player_profiles(args.season)

    output_path = Path(args.output) if args.output else None

    if args.format == "table":
        print_table(rows, args.limit)
    elif args.format == "json":
        write_json(rows, output_path)
    elif args.format == "csv":
        write_csv(rows, output_path)


if __name__ == "__main__":
    main()