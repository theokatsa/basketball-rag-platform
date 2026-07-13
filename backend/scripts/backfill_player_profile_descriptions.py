import argparse
from sqlalchemy import text

from db_utils import engine


def _format_pct(value):
    if value is None:
        return None
    return f"{value * 100:.1f}%"


def build_description(row):
    parts = [row["full_name"]]

    position = row.get("position")
    if position:
        parts.append(f"is a {position.lower().strip()}")
    else:
        parts.append("is a player")

    if row.get("team_name"):
        parts.append(f"for the {row['team_name']}")

    summary_bits = []
    if row.get("games_played") is not None:
        summary_bits.append(f"played {int(row['games_played'])} games")
    if row.get("points") is not None:
        summary_bits.append(f"averaged {row['points']:.1f} points")
    if row.get("rebounds") is not None:
        summary_bits.append(f"{row['rebounds']:.1f} rebounds")
    if row.get("assists") is not None:
        summary_bits.append(f"{row['assists']:.1f} assists")
    if row.get("steals") is not None:
        summary_bits.append(f"{row['steals']:.1f} steals")
    if row.get("blocks") is not None:
        summary_bits.append(f"{row['blocks']:.1f} blocks")
    if row.get("turnovers") is not None:
        summary_bits.append(f"{row['turnovers']:.1f} turnovers")

    efficiency_bits = []
    for label, key in [
        ("field goal percentage", "field_goal_pct"),
        ("three point percentage", "three_point_pct"),
        ("free throw percentage", "free_throw_pct"),
        ("true shooting percentage", "true_shooting_pct"),
    ]:
        pct = _format_pct(row.get(key))
        if pct:
            efficiency_bits.append(f"{label} of {pct}")

    profile = ". ".join([" ".join(parts), " and ".join(summary_bits) if summary_bits else ""]).strip(". ")

    if efficiency_bits:
        profile = f"{profile}. He also has a {'; '.join(efficiency_bits)}."
    else:
        profile = f"{profile}."

    return profile


def fetch_profiles(season: str | None):
    sql = text(
        """
        select pp.id,
               pp.player_id,
               p.full_name,
               pp.season,
               pp.position,
               t.full_name as team_name,
               ps.games_played,
               ps.minutes,
               ps.points,
               ps.rebounds,
               ps.assists,
               ps.steals,
               ps.blocks,
               ps.turnovers,
               ps.field_goal_pct,
               ps.three_point_pct,
               ps.free_throw_pct,
               ps.usage_rate,
               ps.true_shooting_pct,
               ps.player_efficiency_rating
        from player_profiles pp
        join players p on p.id = pp.player_id
        left join teams t on t.id = pp.team_id
        left join lateral (
            select s.games_played,
                   s.minutes,
                   s.points,
                   s.rebounds,
                   s.assists,
                   s.steals,
                   s.blocks,
                   s.turnovers,
                   s.field_goal_pct,
                   s.three_point_pct,
                   s.free_throw_pct,
                   s.usage_rate,
                   s.true_shooting_pct,
                   s.player_efficiency_rating
            from player_season_stats s
            where s.player_id = pp.player_id
            order by s.season desc
            limit 1
        ) ps on true
        where (:season is null or pp.season = :season)
          and (pp.description is null or pp.description = '')
        order by p.full_name
        """
    )

    with engine.begin() as conn:
        return [dict(row) for row in conn.execute(sql, {"season": season}).mappings().all()]


def update_descriptions(rows):
    update_sql = text(
        """
        update player_profiles
        set description = :description
        where id = :id
        """
    )

    updated = 0
    with engine.begin() as conn:
        for row in rows:
            description = build_description(row)
            conn.execute(update_sql, {"id": row["id"], "description": description})
            updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill missing player profile descriptions from existing database data")
    parser.add_argument("--season", default=None, help="Optional season filter, e.g. 2024-25")
    args = parser.parse_args()

    rows = fetch_profiles(args.season)
    updated = update_descriptions(rows)

    print(f"Backfilled {updated} player profile descriptions.")


if __name__ == "__main__":
    main()