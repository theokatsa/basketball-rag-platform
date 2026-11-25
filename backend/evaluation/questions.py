"""Evaluation questions with ground truth taken from the raw tables by SQL.

The truth queries read player_season_stats, player_box_scores, team_box_scores, shot_charts...
and never rag_documents, so a mistake in the index cannot also hide in the answer key.

target "entity": any document about a correct player/team counts (ranking questions).
target "doc":    the right kind of document about the right entity is required (lookups).
split "dev" may be looked at while developing; "test" is only for reporting.
"""

Q = []


def question(split, group, text, sql, target="entity", kind=None):
    Q.append({"id": len(Q) + 1, "split": split, "group": group, "text": text, "sql": sql, "target": target, "kind": kind})


BASE = """from player_season_stats s join players p on p.id = s.player_id
 left join player_profiles pp on pp.player_id = s.player_id left join teams t on t.id = s.team_id
 where s.season = '2024-25' and s.games_played >= 20 and s.minutes >= 12"""


def top(order, where="true", n=10):
    return f"select 'player:' || s.player_id {BASE} and {where} order by {order} limit {n}"


def every(where):
    return f"select 'player:' || s.player_id {BASE} and {where}"


def player(name):
    return f"select 'player:' || id from players where full_name = '{name}'"


def team(nickname):
    return f"select 'team:' || nba_team_id from teams where nickname = '{nickname}'"


def team_rank(expression, n=3):
    """Teams ordered by a season aggregate of their own box scores (o = opponent's row)."""
    return f"""select 'team:' || b.nba_team_id from team_box_scores b
      join team_box_scores o on o.nba_game_id = b.nba_game_id and o.nba_team_id <> b.nba_team_id
      where b.season = '2024-25' group by b.nba_team_id order by {expression} limit {n}"""


def games(a, b):
    return f"""select 'game:' || g.nba_game_id from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id
      join teams o on o.nba_team_id = g.opponent_nba_team_id
      where g.season = '2024-25' and t.nickname = '{a}' and o.nickname = '{b}'"""


POSS = "(sum({0}.fga) + 0.44 * sum({0}.fta) - sum({0}.oreb) + sum({0}.tov))"
OWN, OPP = POSS.format("b"), POSS.format("o")

# ---- development set
question("dev", "ranking", "Who are the best rim protectors?", top("s.blocks desc"))
question("dev", "ranking", "Which players are the top rebounders in the league?", top("s.rebounds desc"))
question("dev", "filter", "Big men who average at least 10 rebounds and 3 assists", every("s.rebounds >= 10 and s.assists >= 3 and (pp.position like '%Center%' or pp.position like '%Forward%')"))
question("dev", "filter", "Centers under 25 who block shots", top("s.blocks desc", "pp.age < 25 and pp.position like '%Center%'"))
question("dev", "team", "Which team had the best defense?", team_rank(f"sum(o.points) / {OPP}"))
question("dev", "team", "What was the Boston Celtics' record?", team("Celtics"), "doc", "team_season")
question("dev", "shooting", "Is Jayson Tatum good from the corner three?", player("Jayson Tatum"), "doc", "shot_profile")
question("dev", "matchup", "Who guards Stephen Curry best?", player("Stephen Curry"), "doc", "matchups")
question("dev", "pairs", "Which duo on the Celtics works best together?", team("Celtics"), "doc", "pairs")
question("dev", "game", "What happened when the Lakers played the Warriors?", games("Lakers", "Warriors"), "doc", "game")
question("dev", "lookup", "How many assists did Trae Young average?", player("Trae Young"), "doc", "player_season")
question("dev", "paraphrase", "Who keeps opponents from scoring near the basket?", top("s.blocks desc"))

question("dev", "paraphrase", "Elite floor generals", top("s.assists desc"))
question("dev", "paraphrase", "Snipers from downtown", top("(select sum(b.tpm) from player_box_scores b where b.player_id = s.player_id and b.season = s.season) desc"))
question("dev", "paraphrase", "Who is careless with the basketball?", top("s.turnovers desc"))
question("dev", "paraphrase", "Who grabs loose balls off missed shots?", top("s.rebounds desc"))
question("dev", "paraphrase", "Bucket getters who can carry an offense", top("s.points desc"))

# ---- held-out test set
question("test", "ranking", "Who are the best playmakers in the league?", top("s.assists desc"))
question("test", "ranking", "Show me the leading scorers", top("s.points desc"))
question("test", "ranking", "Which guards steal the ball the most?", top("s.steals desc", "pp.position like '%Guard%'"))
question("test", "ranking", "Who turns the ball over the most?", top("s.turnovers desc"))
question("test", "filter", "Players averaging more than 25 points and 5 assists", every("s.points > 25 and s.assists > 5"))
question("test", "filter", "Forwards younger than 23 with at least 5 rebounds per game", every("pp.age < 23 and pp.position like '%Forward%' and s.rebounds >= 5"))
question("test", "filter", "Rockets players who score over 15 points a game", every("t.nickname = 'Rockets' and s.points > 15"))
question("test", "filter", "Guards on the Thunder who average 10 or more points", every("t.nickname = 'Thunder' and pp.position like '%Guard%' and s.points >= 10"))
question("test", "filter", "Veterans over 34 who still score at least 15 points", every("pp.age > 34 and s.points >= 15"))
question("test", "team", "Which team scored most efficiently on offense?", team_rank(f"sum(b.points) / {OWN} desc"))
question("test", "team", "Which teams won the most games?", team_rank("count(*) filter (where b.won) desc"))
question("test", "team", "Which team took the most three-pointers?", team_rank("sum(b.tpa) desc"))
question("test", "team", "How good was Oklahoma City on defense?", team("Thunder"), "doc", "team_season")
question("test", "team", "Which team had the worst defense?", team_rank(f"sum(o.points) / {OPP} desc"))
question("test", "shooting", "Where does Devin Booker take most of his shots?", player("Devin Booker"), "doc", "shot_profile")
question("test", "shooting", "How well does Anthony Edwards finish at the rim?", player("Anthony Edwards"), "doc", "shot_profile")
question("test", "shooting", "DeMar DeRozan mid-range shooting", player("DeMar DeRozan"), "doc", "shot_profile")
question("test", "matchup", "Which defenders gave Luka Doncic the most trouble?", player("Luka Dončić"), "doc", "matchups")
question("test", "matchup", "Who struggled to score against Dyson Daniels?", player("Dyson Daniels"), "doc", "matchups")
question("test", "pairs", "Which Nuggets players have the best chemistry on the court?", team("Nuggets"), "doc", "pairs")
question("test", "pairs", "Best two-man combination for the Cavaliers", team("Cavaliers"), "doc", "pairs")
question("test", "form", "How did Cade Cunningham finish the season?", player("Cade Cunningham"), "doc", "form")
question("test", "form", "Was Jalen Green in good form over his last games?", player("Jalen Green"), "doc", "form")
question("test", "game", "Results of Knicks against 76ers games", games("Knicks", "76ers"), "doc", "game")
question("test", "game", "Did the Bucks beat the Pacers?", games("Bucks", "Pacers"), "doc", "game")
question("test", "lookup", "What position does Alperen Sengun play?", player("Alperen Sengun"), "doc", "player_season")
question("test", "lookup", "Free throw percentage of Shai Gilgeous-Alexander", player("Shai Gilgeous-Alexander"), "doc", "player_season")
question("test", "lookup", "Compare Jokic and Embiid", "select 'player:' || id from players where full_name in ('Nikola Jokić', 'Joel Embiid')", "doc", "player_season")
question("test", "paraphrase", "Who creates the most open looks for his teammates?", top("s.assists desc"))
question("test", "paraphrase", "Guys who clean the glass", top("s.rebounds desc"))
question("test", "paraphrase", "Who puts the ball in the basket more than anyone?", top("s.points desc"))
question("test", "paraphrase", "Pickpockets who jump into passing lanes", top("s.steals desc"))

# Questions this database cannot answer: the system should decline, not improvise.
UNANSWERABLE = [
    "Who won the 1998 NBA Finals?",
    "What is LeBron James's salary?",
    "How many points did Michael Jordan average in 1990-91?",
    "Who will win MVP next year?",
    "What is the capital of France?",
    "Which WNBA player leads in assists?",
]
