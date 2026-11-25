"""Turns the relational data into retrievable documents ("chunks").

One document answers one kind of question about one entity. Each carries
  * content  - sentences, for embedding, keyword search and the language model
  * meta     - the same facts as numbers, for exact filters and rankings
MiniLM reads about 256 word pieces, so every document stays short.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import text

from app.services.cache import rows
from app.services.form_service import form
from app.services.insight_service import _baselines, _edge, load_profiles
from app.services.stat_vectors import FEATURES, SeasonVectors, describe, qualifies
from app.services.text_utils import normalize_name

MIN_ZONE_SHOTS, MIN_PLAYER_SHOTS = 10, 60
MIN_MATCHUP_POSSESSIONS, MIN_PAIR_MINUTES = 25, 200
FORM_WINDOW = 10


@dataclass
class Document:
    kind: str
    entity: str
    season: str
    title: str
    content: str
    player_ids: list[int] = field(default_factory=list)
    team_ids: list[int] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.entity}:{self.season}"

    @property
    def embedded_text(self) -> str:
        return f"{self.title}. {self.content}"

    @property
    def search_text(self) -> str:
        return normalize_name(self.embedded_text)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.embedded_text.encode("utf-8")).hexdigest()


def pct(value) -> str:
    return f"{(value or 0) * 100:.1f}%"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _numbers(row: dict, names) -> dict:
    return {name: round(float(row[name]), 4) for name in names if row.get(name) is not None}


def player_documents(db, vectors: SeasonVectors) -> list[Document]:
    advanced = {r["player_id"]: r for r in rows(db, text("select * from player_advanced_stats where season = :s"), {"s": vectors.season})}
    teams = {r["id"]: r["nba_team_id"] for r in rows(db, text("select s.player_id as id, t.nba_team_id from player_season_stats s join teams t on t.id = s.team_id where s.season = :s"), {"s": vectors.season})}
    documents = []
    for i, row in enumerate(vectors.rows):
        pid = row["player_id"]
        content = describe(vectors, pid)
        a = advanced.get(pid)
        if a and a["usg_pct"] is not None:
            content += (
                f" Advanced: {pct(a['usg_pct'])} usage, {pct(a['ts_pct'])} true shooting, assisted {pct(a['ast_pct'])} of teammates' baskets,"
                f" offensive rating {a['off_rating']:.1f}, defensive rating {a['def_rating']:.1f}, net rating {a['net_rating']:+.1f}."
            )
            if (a["defended_fga"] or 0) >= 100:
                diff = (a["defended_fg_diff"] or 0) * 100
                content += f" Opponents shot {abs(diff):.1f} percentage points {'worse' if diff < 0 else 'better'} than usual when guarded by this player."
        meta = _numbers(row, ["games_played", "age", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "field_goal_pct", "three_point_pct", "free_throw_pct", "three_point_attempts"])
        if a:
            meta |= _numbers(a, ["usg_pct", "ts_pct", "off_rating", "def_rating", "net_rating"])
        meta |= {f"z_{name}": round(float(vectors.raw[i][j]), 4) for j, name in enumerate(FEATURES)}
        meta |= {"position": row["position"] or "", "qualified": qualifies(row)}
        documents.append(Document("player_season", f"player:{pid}", vectors.season, f"{row['full_name']} {vectors.season} season", content, [pid], [teams[pid]] if pid in teams else [], meta))
    return documents


_ZONES = {
    "Restricted Area": "at the rim (restricted area)", "In The Paint (Non-RA)": "in the paint outside the restricted area", "Mid-Range": "from mid-range",
    "Left Corner 3": "on left corner threes", "Right Corner 3": "on right corner threes", "Above the Break 3": "on above-the-break threes",
}


def shot_documents(db, vectors: SeasonVectors) -> list[Document]:
    found = rows(db, text("""
        select player_id, shot_zone_basic as zone, count(*) as tries, sum(case when shot_made then 1 else 0 end) as made
        from shot_charts where season = :s and player_id is not null and shot_zone_basic <> 'Backcourt' group by 1, 2
    """), {"s": vectors.season})
    league: dict[str, list[int]] = {}
    players: dict[int, list[dict]] = {}
    for r in found:
        total = league.setdefault(r["zone"], [0, 0])
        total[0] += r["tries"]
        total[1] += r["made"]
        players.setdefault(r["player_id"], []).append(r)
    documents = []
    for pid, zones in players.items():
        shots = sum(z["tries"] for z in zones)
        if shots < MIN_PLAYER_SHOTS or pid not in vectors.index:
            continue
        name = vectors.rows[vectors.index[pid]]["full_name"]
        zones.sort(key=lambda z: -z["tries"])
        parts = []
        for z in zones:
            if z["tries"] < MIN_ZONE_SHOTS:
                continue
            base = league[z["zone"]][1] / league[z["zone"]][0]
            parts.append(f"{z['made']} of {z['tries']} ({pct(z['made'] / z['tries'])}, league {pct(base)}) {_ZONES[z['zone']]}")
        best = [z for z in zones if z["tries"] >= MIN_ZONE_SHOTS]
        content = f"{name} took {shots} tracked shots in {vectors.season}, most often {_ZONES[best[0]['zone']]} ({pct(best[0]['tries'] / shots)} of them). Shooting by zone: " + "; ".join(parts) + "."
        documents.append(Document("shot_profile", f"player:{pid}", vectors.season, f"{name} shot locations {vectors.season}", content, [pid], [], {"shots": shots}))
    return documents


def matchup_documents(db, vectors: SeasonVectors) -> list[Document]:
    if not (bases := _baselines(db)):
        return []
    profiles = load_profiles(db)
    guarded_by: dict[int, list] = {}
    guarded: dict[int, list] = {}
    for m in rows(db, text("select off_player_id as o, def_player_id as d, possessions, points from player_matchups where season = :s and possessions >= :p"), {"s": vectors.season, "p": MIN_MATCHUP_POSSESSIONS}):
        base = bases.get(m["o"])
        if base is None or m["o"] not in profiles or m["d"] not in profiles:
            continue
        item = {**m, "edge": _edge(m["points"], m["possessions"], base), "rate": m["points"] / m["possessions"] * 100, "usual": base * 100}
        guarded_by.setdefault(m["o"], []).append(item)
        guarded.setdefault(m["d"], []).append(item)

    def names(items, side):
        return "; ".join(
            f"{profiles[m[side]]['full_name']} ({m['rate']:.1f} over {m['possessions']:.0f}"
            + (f", usual {m['usual']:.1f})" if side == "o" else ")")
            for m in items
        )

    documents = []
    for pid in guarded_by.keys() | guarded.keys():
        if pid not in vectors.index:
            continue
        name = profiles[pid]["full_name"]
        parts = []
        # Ordered by the edge shrunk toward the scorer's average, so a lucky 25 possessions does not win.
        if faced := sorted(guarded_by.get(pid, []), key=lambda m: m["edge"]):
            parts.append(f"{name} usually scores {bases[pid] * 100:.1f} points per 100 matchup possessions. Brackets: points per 100 over possessions.")
            hard, easy = [m for m in faced[:4] if m["edge"] < 0], [m for m in faced[::-1][:2] if m["edge"] > 0]
            if hard:
                parts.append(f"Defenders who guarded {name} best: {names(hard, 'd')}.")
            if easy:
                parts.append(f"Easiest defenders: {names(easy, 'd')}.")
        if held := sorted(guarded.get(pid, []), key=lambda m: m["edge"]):
            if good := [m for m in held[:3] if m["edge"] < 0]:
                parts.append(f"Scorers who struggled against {name}: {names(good, 'o')}.")
        if parts:
            documents.append(Document("matchups", f"player:{pid}", vectors.season, f"{name} defensive matchups {vectors.season}", " ".join(parts), [pid]))
    return documents


def form_documents(db, vectors: SeasonVectors) -> list[Document]:
    documents = []
    labels = {"points": "points", "reb": "rebounds", "ast": "assists", "stl": "steals", "blk": "blocks", "tov": "turnovers", "minutes": "minutes"}
    for item in form(db, FORM_WINDOW):
        pid, stats = item["player_id"], item["stats"]
        if pid not in vectors.index or stats["minutes"]["now"] < 12:
            continue
        name = vectors.rows[vectors.index[pid]]["full_name"]
        lines = [f"{stats[k]['now']:.1f} {label} (before: {stats[k]['before']:.1f})" for k, label in labels.items() if k in stats]
        shooting = [f"{stats[k]['now']:.1f}% {label} (before: {stats[k]['before']:.1f}%)" for k, label in (("ts", "true shooting"), ("three", "from three")) if k in stats]
        change = stats["game_score"]["surprise"] if "game_score" in stats else 0
        verdict = "clearly better than earlier, a hot finish" if change >= 1.5 else "clearly worse than earlier, a cold finish" if change <= -1.5 else "close to the usual level"
        content = f"Form at the end of the season: in the last {FORM_WINDOW} games of {vectors.season} {name} averaged {', '.join(lines)}"
        content += (f", shooting {' and '.join(shooting)}" if shooting else "") + f". Overall this was {verdict}."
        documents.append(Document("form", f"player:{pid}", vectors.season, f"{name} recent form, last {FORM_WINDOW} games of {vectors.season}", content, [pid], [], {"change": change}))
    return documents


def team_documents(db, vectors: SeasonVectors) -> list[Document]:
    found = rows(db, text("""
        select t.nba_team_id, t.full_name, count(*) as games, sum(b.won::int) as wins,
               avg(b.points)::float as points, avg(o.points)::float as allowed, avg(b.reb)::float as rebounds, avg(b.ast)::float as assists,
               avg(b.tov)::float as turnovers, avg(b.stl)::float as steals, avg(b.blk)::float as blocks, avg(b.tpa)::float as threes, (sum(b.tpm)::float / sum(b.tpa)) as three_pct,
               (sum(b.won::int) filter (where b.is_home)) as home_wins, (count(*) filter (where b.is_home)) as home_games,
               (100 * sum(b.points) / sum(b.fga + 0.44 * b.fta - b.oreb + b.tov))::float as off_rating,
               (100 * sum(o.points) / sum(o.fga + 0.44 * o.fta - o.oreb + o.tov))::float as def_rating,
               avg(b.fga + 0.44 * b.fta - b.oreb + b.tov)::float as pace
        from team_box_scores b join teams t on t.nba_team_id = b.nba_team_id
        join team_box_scores o on o.nba_game_id = b.nba_game_id and o.nba_team_id <> b.nba_team_id
        where b.season = :s group by 1, 2
    """), {"s": vectors.season})
    for r in found:
        r["net_rating"] = r["off_rating"] - r["def_rating"]

    def rank(key, low=False):
        ordered = sorted(found, key=lambda r: r[key] if low else -r[key])
        return {r["nba_team_id"]: n for n, r in enumerate(ordered, 1)}

    ranks = {k: rank(k, low) for k, low in (("wins", False), ("off_rating", False), ("def_rating", True), ("net_rating", False), ("threes", False), ("three_pct", False), ("rebounds", False), ("assists", False), ("turnovers", True), ("pace", False))}
    by_team: dict[str, list[dict]] = {}
    for row in vectors.rows:
        if row["team_name"] and qualifies(row):
            by_team.setdefault(row["team_name"], []).append(row)
    documents = []
    for r in found:
        tid, name = r["nba_team_id"], r["full_name"]

        def place(key):
            return ordinal(ranks[key][tid])

        squad = by_team.get(name, [])
        leaders = [f"{best['full_name']} ({best[k]:.1f} {k})" for k in ("points", "rebounds", "assists") if squad and (best := max(squad, key=lambda p: p[k] or 0))]
        content = (
            f"The {name} won {r['wins']} and lost {r['games'] - r['wins']} of their {r['games']} games in {vectors.season} ({place('wins')} most wins), {r['home_wins']} of {r['home_games']} at home."
            f" Offense: {r['points']:.1f} points per game, offensive rating {r['off_rating']:.1f} ({place('off_rating')} of {len(found)})."
            f" Defense: {r['allowed']:.1f} points allowed, defensive rating {r['def_rating']:.1f} ({place('def_rating')} best). Net rating {r['net_rating']:+.1f} ({place('net_rating')})."
            f" Style: pace {r['pace']:.1f} possessions ({place('pace')}), {r['threes']:.1f} three-point attempts per game ({place('threes')}) at {pct(r['three_pct'])} ({place('three_pct')}),"
            f" {r['rebounds']:.1f} rebounds ({place('rebounds')}), {r['assists']:.1f} assists ({place('assists')}), {r['turnovers']:.1f} turnovers ({place('turnovers')} fewest)."
        )
        if leaders:
            content += f" Leaders: {', '.join(leaders)}."
        meta = _numbers(r, ["wins", "points", "allowed", "rebounds", "assists", "turnovers", "steals", "blocks", "threes", "three_pct", "off_rating", "def_rating", "net_rating", "pace"])
        documents.append(Document("team_season", f"team:{tid}", vectors.season, f"{name} team season {vectors.season}", content, [], [tid], meta))
    return documents


def pair_documents(db, vectors: SeasonVectors) -> list[Document]:
    teams = {r["nba_team_id"]: r["full_name"] for r in rows(db, text("select nba_team_id, full_name from teams"))}
    by_team: dict[int, list[dict]] = {}
    for r in rows(db, text("""
        select x.*, a.full_name as a_name, b.full_name as b_name from player_pairs x join players a on a.id = x.player_a join players b on b.id = x.player_b
        where x.season = :s and x.minutes >= :m and x.net_rating is not null order by x.net_rating desc
    """), {"s": vectors.season, "m": MIN_PAIR_MINUTES}):
        by_team.setdefault(r["nba_team_id"], []).append(r)

    def line(p):
        return f"{p['a_name']} and {p['b_name']} ({p['net_rating']:+.1f} points per 100 possessions in {p['minutes']:.0f} minutes together)"

    documents = []
    for tid, pairs in by_team.items():
        best, worst = pairs[:5], pairs[5:][-3:]
        content = f"Two-man combinations of the {teams[tid]} in {vectors.season} with at least {MIN_PAIR_MINUTES} shared minutes. Best duos and chemistry on the court by net rating: " + "; ".join(map(line, best)) + "."
        if worst:
            content += " Weakest duos: " + "; ".join(map(line, worst[::-1])) + "."
        people = list(dict.fromkeys(p[k] for p in best + worst for k in ("player_a", "player_b")))
        documents.append(Document("pairs", f"team:{tid}", vectors.season, f"{teams[tid]} duos {vectors.season}", content, people, [tid]))
    return documents


def game_documents(db, vectors: SeasonVectors) -> list[Document]:
    sides: dict[str, list[dict]] = {}
    for r in rows(db, text("""
        select b.nba_game_id, b.game_date, b.is_home, b.won, b.points, b.nba_team_id, t.full_name,
               (select max(period) from team_period_scores p where p.nba_game_id = b.nba_game_id) as periods
        from team_box_scores b join teams t on t.nba_team_id = b.nba_team_id where b.season = :s
    """), {"s": vectors.season}):
        sides.setdefault(r["nba_game_id"], []).append(r)
    stars: dict[tuple, list[dict]] = {}
    for r in rows(db, text("""
        select * from (
            select b.nba_game_id, b.nba_team_id, b.player_id, p.full_name, b.points, b.reb, b.ast,
                   row_number() over (partition by b.nba_game_id, b.nba_team_id order by b.points + 0.7 * b.reb + 0.7 * b.ast desc) as n
            from player_box_scores b join players p on p.id = b.player_id where b.season = :s
        ) ranked where n <= 2
    """), {"s": vectors.season}):
        stars.setdefault((r["nba_game_id"], r["nba_team_id"]), []).append(r)
    documents = []
    for game_id, pair in sides.items():
        if len(pair) != 2:
            continue
        winner, loser = sorted(pair, key=lambda s: not s["won"])
        day = f"{winner['game_date'].day} {winner['game_date']:%B %Y}"
        place = "at home" if winner["is_home"] else "away" if loser["is_home"] else "at a neutral site"
        extra = " after overtime" if (winner["periods"] or 4) > 4 else ""
        content = f"On {day} the {winner['full_name']} beat the {loser['full_name']} {winner['points']}-{loser['points']} {place}{extra}."
        people = []
        for side in (winner, loser):
            best = sorted(stars.get((game_id, side["nba_team_id"]), []), key=lambda s: s["n"])
            people += [s["player_id"] for s in best]
            lines = [f"{s['full_name']} {s['points']} points, {s['reb']} rebounds, {s['ast']} assists" for s in best]
            content += f" Best for the {side['full_name']}: {'; '.join(lines)}."
        documents.append(Document(
            "game", f"game:{game_id}", vectors.season, f"{winner['full_name']} vs {loser['full_name']}, {day}", content, people,
            [winner["nba_team_id"], loser["nba_team_id"]], {"date": winner["game_date"].isoformat()},
        ))
    return documents


BUILDERS = [player_documents, shot_documents, matchup_documents, form_documents, team_documents, pair_documents, game_documents]


def build_corpus(db, vectors: SeasonVectors) -> list[Document]:
    return [document for build in BUILDERS for document in build(db, vectors)]
