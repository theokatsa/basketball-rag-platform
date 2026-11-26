from sqlalchemy import text

from app.services.cache import cached, rows
from app.core.config import ACTIVE_SEASON_SQL

EAST = {"ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"}
COUNTS = ["points", "opponent_points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf"]
LATEST = ACTIVE_SEASON_SQL
GAME_SCORE = "(b.points + 0.4 * b.fgm - 0.7 * b.fga - 0.4 * (b.fta - b.ftm) + 0.7 * b.oreb + 0.3 * b.dreb + b.stl + 0.7 * b.ast + 0.7 * b.blk - 0.4 * b.pf - b.tov)::float"


def list_games(db):
    """Every game of the season, newest first, with the best performer by Game Score."""
    def load():
        games = rows(db, text(f"""
            select h.nba_game_id as game_id, h.game_date::text as game_date, h.season,
                   h.nba_team_id as home_id, a.nba_team_id as away_id,
                   h.points as home_points, a.points as away_points, h.minutes > 245 as overtime
            from team_box_scores h
            join team_box_scores a on a.nba_game_id = h.nba_game_id and a.nba_team_id <> h.nba_team_id
            where h.is_home and h.season = {LATEST}
            order by h.game_date desc, h.nba_game_id desc
        """))
        leaders = rows(db, text(f"""
            select distinct on (b.nba_game_id) b.nba_game_id, b.player_id, b.points, b.reb, b.ast, {GAME_SCORE} as game_score
            from player_box_scores b where b.season = {LATEST}
            order by b.nba_game_id, {GAME_SCORE} desc
        """))
        best = {r.pop("nba_game_id"): r for r in leaders}
        return [{**g, "best": best.get(g["game_id"])} for g in games]

    return cached("games", load)


def get_game(db, game_id: str):
    teams = rows(db, text("""
        select b.*, b.game_date::text as game_date, t.abbreviation, t.full_name
        from team_box_scores b join teams t on t.nba_team_id = b.nba_team_id
        where b.nba_game_id = :id order by b.is_home
    """), {"id": game_id})
    if len(teams) != 2:
        return None
    players = rows(db, text(f"""
        select b.*, b.game_date::text as game_date, p.full_name, p.nba_player_id, {GAME_SCORE} as game_score
        from player_box_scores b join players p on p.id = b.player_id
        where b.nba_game_id = :id order by b.minutes desc, b.points desc
    """), {"id": game_id})
    shots = rows(db, text("""
        select sc.player_id, t.nba_team_id, sc.period, sc.minutes_remaining, sc.seconds_remaining, sc.shot_type,
               sc.action_type, sc.shot_distance, sc.loc_x, sc.loc_y, sc.shot_made
        from shot_charts sc join teams t on t.id = sc.team_id
        where sc.nba_game_id = :id
        order by sc.period, sc.minutes_remaining desc, sc.seconds_remaining desc
    """), {"id": game_id})
    periods = rows(db, text("select nba_team_id, period, points from team_period_scores where nba_game_id = :id order by period"), {"id": game_id})
    return {"game_id": game_id, "teams": teams, "players": players, "shots": shots, "periods": periods}


def best_games(db, limit: int):
    """Best single games of the season by Game Score."""
    return rows(db, text(f"""
        select b.player_id, b.nba_game_id as game_id, b.game_date::text as game_date, b.points, b.reb as rebounds, b.ast as assists,
               b.stl as steals, b.blk as blocks, b.fgm as field_goals_made, b.fga as field_goals_attempted, {GAME_SCORE} as game_score,
               b.nba_team_id as team_id, t.opponent_nba_team_id as opponent_id, o.abbreviation as opponent, t.is_home, t.won,
               t.points as team_points, t.opponent_points
        from player_box_scores b
        join team_box_scores t on t.nba_game_id = b.nba_game_id and t.nba_team_id = b.nba_team_id
        join teams o on o.nba_team_id = t.opponent_nba_team_id
        where b.season = {LATEST}
        order by game_score desc, b.nba_game_id limit :limit
    """), {"limit": limit})


def _factors(total: dict, games: int) -> dict:
    possessions = total["fga"] + 0.44 * total["fta"] - total["oreb"] + total["tov"]
    return {
        **{key: total[key] / games for key in COUNTS},
        "possessions": possessions / games,
        "off_rating": 100 * total["points"] / possessions,
        "fg_pct": 100 * total["fgm"] / total["fga"], "three_pct": 100 * total["tpm"] / total["tpa"], "ft_pct": 100 * total["ftm"] / total["fta"],
        "efg": 100 * (total["fgm"] + 0.5 * total["tpm"]) / total["fga"],
        "ts": 100 * total["points"] / (2 * (total["fga"] + 0.44 * total["fta"])),
        "tov_pct": 100 * total["tov"] / possessions,
        "ft_rate": 100 * total["ftm"] / total["fga"],
        "three_rate": 100 * total["tpa"] / total["fga"],
    }


def _record(games):
    wins = sum(g["won"] for g in games)
    return [wins, len(games) - wins]


def team_summaries(db):
    def load():
        lines = rows(db, text(f"""
            select b.*, b.game_date::text as day, t.abbreviation, t.full_name, t.city, t.nickname, t.year_founded
            from team_box_scores b join teams t on t.nba_team_id = b.nba_team_id
            where b.season = {LATEST} order by b.game_date, b.nba_game_id
        """))
        grouped: dict[int, list[dict]] = {}
        for line in lines:
            grouped.setdefault(line["nba_team_id"], []).append(line)
        by_key = {(line["nba_game_id"], line["nba_team_id"]): line for line in lines}
        result = []
        for team_id, own in grouped.items():
            against = [by_key[(g["nba_game_id"], g["opponent_nba_team_id"])] for g in own]
            total = {k: sum(g[k] for g in own) for k in COUNTS}
            allowed = {k: sum(g[k] for g in against) for k in COUNTS}
            n = len(own)
            offense, defense = _factors(total, n), _factors(allowed, n)
            streak = 1
            for g in reversed(own[:-1]):
                if g["won"] != own[-1]["won"]:
                    break
                streak += 1
            first, (wins, losses) = own[0], _record(own)
            result.append({
                "team_id": team_id, "abbreviation": first["abbreviation"], "name": first["full_name"],
                "city": first["city"], "nickname": first["nickname"], "founded": first["year_founded"],
                "conference": "East" if first["abbreviation"] in EAST else "West",
                "wins": wins, "losses": losses, "win_pct": wins / n,
                "home": _record([g for g in own if g["is_home"]]), "away": _record([g for g in own if not g["is_home"]]),
                "last10": _record(own[-10:]), "close": _record([g for g in own if abs(g["points"] - g["opponent_points"]) <= 5]),
                "streak": streak if own[-1]["won"] else -streak,
                "margin": (total["points"] - total["opponent_points"]) / n,
                "pace": 48 * (offense["possessions"] + defense["possessions"]) / 2 / (sum(g["minutes"] for g in own) / 5 / n),
                "offense": {**offense, "oreb_pct": 100 * total["oreb"] / (total["oreb"] + allowed["dreb"])},
                "defense": {**defense, "oreb_pct": 100 * allowed["oreb"] / (allowed["oreb"] + total["dreb"])},
                "net_rating": offense["off_rating"] - defense["off_rating"],
                "results": [{"game_id": g["nba_game_id"], "date": g["day"], "opponent_id": g["opponent_nba_team_id"], "home": g["is_home"], "won": g["won"], "points": g["points"], "opponent_points": g["opponent_points"]} for g in own],
            })
        return sorted(result, key=lambda t: -t["win_pct"])

    return cached("team_summaries", load)
