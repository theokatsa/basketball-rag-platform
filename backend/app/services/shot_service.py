"""Court zones, decided from shot coordinates so every shot belongs to exactly one area.

The same rules live in frontend/src/components/CourtZones.tsx (zoneOf); keep them in step.
"""

from sqlalchemy import text

from app.services.cache import cached, rows
from app.core.config import ACTIVE_SEASON_SQL

ZONE_SQL = """
case
  when sc.loc_y > 418 then 'backcourt'
  when sc.shot_type like '3%' then
    case
      when sc.loc_y <= 89 and abs(sc.loc_x) >= 200 then case when sc.loc_x < 0 then 'corner-L' else 'corner-R' end
      when sc.loc_x * sc.loc_x + sc.loc_y * sc.loc_y >= 78400 then 'deep'
      when abs(sc.loc_x) <= 80 then 'top'
      when sc.loc_y < abs(sc.loc_x) then case when sc.loc_x < 0 then 'wing-L' else 'wing-R' end
      else case when sc.loc_x < 0 then 'slot-L' else 'slot-R' end
    end
  when sc.loc_x * sc.loc_x + sc.loc_y * sc.loc_y <= 1600 then 'rim'
  when abs(sc.loc_x) <= 80 and sc.loc_y <= 70 then 'lane-low'
  when abs(sc.loc_x) <= 80 and sc.loc_y <= 137 then 'lane-high'
  when abs(sc.loc_x) <= 80 and sc.loc_x * sc.loc_x + sc.loc_y * sc.loc_y <= 36100 then 'ft'
  when abs(sc.loc_x) <= 80 then 'key'
  when sc.loc_y < 80 then case when sc.loc_x < 0 then 'base-L' else 'base-R' end
  else case when sc.loc_x < 0 then 'midw-L' else 'midw-R' end
end
"""
OPPONENT_SQL = "case when split_part(sc.matchup, ' vs ', 1) = t.abbreviation then split_part(sc.matchup, ' vs ', 2) else split_part(sc.matchup, ' vs ', 1) end"
SEASON = f"sc.season = {ACTIVE_SEASON_SQL}"
COUNTS = "count(*) as attempts, sum(sc.shot_made::int) as made"


def player_zones(db, opponent: str | None = None):
    def load():
        condition = f"and {OPPONENT_SQL} = :opponent" if opponent else ""
        return rows(db, text(f"""
            select sc.player_id, {ZONE_SQL} as zone, {COUNTS}
            from shot_charts sc left join teams t on t.id = sc.team_id
            where {SEASON} {condition} group by 1, 2
        """), {"opponent": opponent} if opponent else {})

    return cached(("player_zones", opponent), load)


def league_zones(db):
    return cached("league_zones", lambda: rows(db, text(f"select {ZONE_SQL} as zone, {COUNTS} from shot_charts sc where {SEASON} group by 1")))


def team_zones(db, side: str):
    """Zones a team shot from (offense) or gave up (defense)."""
    def load():
        team = "t.nba_team_id" if side == "offense" else "o.nba_team_id"
        join = "" if side == "offense" else f"join teams o on o.abbreviation = {OPPONENT_SQL}"
        return rows(db, text(f"""
            select {team} as team_id, {ZONE_SQL} as zone, {COUNTS}
            from shot_charts sc join teams t on t.id = sc.team_id {join}
            where {SEASON} group by 1, 2
        """))

    return cached(("team_zones", side), load)
