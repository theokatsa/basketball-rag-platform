from statistics import mean, pstdev

from sqlalchemy import text

from app.services.cache import cached, rows
from app.core.config import ACTIVE_SEASON_SQL

STATS = ["points", "reb", "ast", "stl", "blk", "tov", "tpm", "minutes", "plus_minus", "game_score", "fg", "three", "ts"]


def _share(games, made, attempted):
    attempts = sum(g[attempted] for g in games)
    return 100 * sum(g[made] for g in games) / attempts if attempts else None


def _ts(games):
    tries = sum(g["fga"] + 0.44 * g["fta"] for g in games)
    return 100 * sum(g["points"] for g in games) / (2 * tries) if tries else None


def _average(games, stat):
    if stat == "fg":
        return _share(games, "fgm", "fga") if sum(g["fga"] for g in games) >= 20 else None
    if stat == "three":
        return _share(games, "tpm", "tpa") if sum(g["tpa"] for g in games) >= 20 else None
    if stat == "ts":
        return _ts(games) if sum(g["fga"] for g in games) >= 30 else None
    return mean(g[stat] for g in games)


def _single(game, stat):
    value = _share([game], "fgm", "fga") if stat == "fg" else _share([game], "tpm", "tpa") if stat == "three" else _ts([game]) if stat == "ts" else game[stat]
    return None if value is None else round(value, 1)


def form(db, window: int):
    """Each player's last N games against the earlier ones, for every statistic."""
    def load():
        games = rows(db, text(f"""
            select b.*, b.game_date::text as day,
                   (b.points + 0.4 * b.fgm - 0.7 * b.fga - 0.4 * (b.fta - b.ftm) + 0.7 * b.oreb + 0.3 * b.dreb + b.stl + 0.7 * b.ast + 0.7 * b.blk - 0.4 * b.pf - b.tov)::float as game_score
            from player_box_scores b
            where b.season = {ACTIVE_SEASON_SQL} and b.minutes > 0
            order by b.player_id, b.game_date
        """))
        grouped: dict[int, list[dict]] = {}
        for g in games:
            grouped.setdefault(g["player_id"], []).append(g)
        result = []
        for player_id, log in grouped.items():
            if len(log) < max(window + 10, 20):
                continue
            recent, earlier = log[-window:], log[:-window]
            stats = {}
            for stat in STATS:
                now, before = _average(recent, stat), _average(earlier, stat)
                if now is None or before is None:
                    continue
                values = [v for v in (_single(g, stat) for g in earlier) if v is not None]
                spread = pstdev(values) if len(values) > 1 else 0
                # How unusual the change is for this player: the gap in standard errors.
                stats[stat] = {"now": round(now, 2), "before": round(before, 2), "surprise": round((now - before) / (spread / window ** 0.5), 2) if spread else 0, "games": [_single(g, stat) for g in recent]}
            result.append({"player_id": player_id, "games_played": len(log), "last_game": recent[-1]["day"], "stats": stats})
        return result

    return cached(("form", window), load)
