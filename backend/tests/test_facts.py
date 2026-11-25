"""The fact engine on a tiny made-up league whose numbers can be checked by hand."""

import unittest
from unittest.mock import patch

import pandas as pd

from app.services import fact_engine, league_data as data
from app.services.question_reader import parse, standalone, sum_players, Query

TEAMS = pd.DataFrame([
    {"nba_team_id": 1, "full_name": "Boston Celtics", "city": "Boston", "nickname": "Celtics", "abbreviation": "BOS", "year_founded": 1946, "conference": "East"},
    {"nba_team_id": 2, "full_name": "Denver Nuggets", "city": "Denver", "nickname": "Nuggets", "abbreviation": "DEN", "year_founded": 1976, "conference": "West"},
]).set_index("nba_team_id", drop=False)
PEOPLE = pd.DataFrame([
    {"player_id": 10, "full_name": "Jayson Tatum", "position": "Forward", "team": 1, "gp": 4, "mpg": 36, "points": 25.0, "age": 26, "inches": 80, "weight": 210, "experience": 8, "conference": "East"},
    {"player_id": 20, "full_name": "Nikola Jokić", "position": "Center", "team": 2, "gp": 4, "mpg": 36, "points": 27.5, "age": 29, "inches": 83, "weight": 284, "experience": 10, "conference": "West"},
]).set_index("player_id", drop=False)
for column in ("usg_pct", "ast_to", "ast_pct", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "net_rating", "off_rating", "def_rating", "pie", "defended_fga", "defended_fg_pct", "defended_fg_diff", "overall_score", "offense_score", "defense_score"):
    PEOPLE[column] = [10.0, 20.0]

# Four games: Boston wins two, Denver wins two. Boston hosts games 1 and 3.
SCORES = [("g1", "2024-11-01", 110, 100, True), ("g2", "2024-12-25", 95, 105, False), ("g3", "2025-01-10", 120, 99, True), ("g4", "2025-01-20", 101, 102, False)]
PLAYER_POINTS = {10: [40, 10, 30, 20], 20: [20, 30, 25, 35]}
PLAYER_REBOUNDS = {10: [10, 5, 5, 8], 20: [12, 15, 9, 12]}


def make_frames():
    zero = {c: 0 for c in data.SUMS}
    teams, box = [], []
    for n, (game, day, boston, denver, at_boston) in enumerate(SCORES):
        for team, opp, own, other in ((1, 2, boston, denver), (2, 1, denver, boston)):
            home = at_boston == (team == 1)
            row = {"game_id": game, "game_date": pd.Timestamp(day), "team": team, "opp": opp, "home": home, "won": own > other, **zero, "minutes": 240, "points": own, "fga": 90, "fgm": 40, "tpa": 30, "tpm": 10, "fta": 20, "ftm": 15, "reb": 44, "oreb": 10, "dreb": 34, "tov": 12}
            row |= {f"a_{c}": 0 for c in data.SUMS} | {"a_points": other, "a_fga": 90, "a_fta": 20, "a_oreb": 10, "a_tov": 12, "a_dreb": 34, "a_tpm": 10, "a_tpa": 30}
            row |= {"margin": own - other, "overtime": False, **{f"q{q}": own / 4 for q in range(1, 5)}, **{f"a_q{q}": other / 4 for q in range(1, 5)}}
            teams.append(row)
            player = 10 if team == 1 else 20
            points, rebounds = PLAYER_POINTS[player][n], PLAYER_REBOUNDS[player][n]
            box.append({
                "game_id": game, "player_id": player, "team": team, "opp": opp, "home": home, "won": own > other, "margin": own - other, "overtime": False, "game_date": pd.Timestamp(day), **zero,
                "minutes": 36, "points": points, "fga": 20, "fgm": points // 3, "tpa": 8, "tpm": 3, "fta": 5, "ftm": 4, "reb": rebounds, "ast": 10, "plus_minus": own - other,
                "double_doubles": 1, "triple_doubles": int(points >= 10 and rebounds >= 10), "game_score": float(points),
            })
    return pd.DataFrame(teams), pd.DataFrame(box)


TEAM_GAMES, BOX = make_frames()


class Facts(unittest.TestCase):
    def setUp(self):
        for name, frame in (("team_list", TEAMS), ("people", PEOPLE), ("team_games", TEAM_GAMES), ("box_scores", BOX)):
            patcher = patch.object(data, name, lambda db, f=frame: f)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(data, "season_name", lambda db: "2024-25")
        patcher.start()
        self.addCleanup(patcher.stop)

    def say(self, question):
        fact = fact_engine.answer(None, question)
        self.assertIsNotNone(fact, question)
        return fact.answer

    def test_average_total_and_slices(self):
        self.assertIn("averaged 25.0 points", self.say("How many points does Jayson Tatum average?"))
        self.assertIn("averaged 35.0 points at home", self.say("How many points does Tatum average at home?"))
        self.assertIn("averaged 25.0 points in January", self.say("Tatum points per game in January"))
        self.assertIn("averaged 25.0 points in the last 2 games", self.say("Tatum points per game over the last 2 games"))
        self.assertIn("had 100 points", self.say("How many points did Tatum score in total?"))
        self.assertIn("averaged 35.0 points in wins", self.say("What does Tatum average in points when his team wins?"))

    def test_counts_and_highs(self):
        self.assertIn("had 2 games with at least 30 points", self.say("How many 30-point games did Tatum have?"))
        self.assertTrue(self.say("What was Jokic's season high in rebounds?").startswith("Nikola Jokić 15 rebounds"))
        self.assertIn("had 3 triple-doubles", self.say("How many triple-doubles did Jokic have?"))

    def test_bio_and_comparison(self):
        self.assertIn("6'8\"", self.say("How tall is Jayson Tatum?"))
        self.assertTrue(self.say("Who is taller, Jokic or Tatum?").startswith("Nikola Jokić"))
        self.assertTrue(self.say("Who scores more, Tatum or Jokic?").startswith("Nikola Jokić: 27.5"))

    def test_records(self):
        self.assertIn("were 2-2", self.say("What was the Celtics record?"))
        self.assertIn("were 2-0 at home", self.say("What was the Celtics' home record?"))
        self.assertIn("won 2 of 4 games against", self.say("How many times did the Celtics beat the Nuggets?"))
        self.assertIn("streak of the Boston Celtics was 1 game,", self.say("Longest winning streak of the Celtics"))

    def test_extremes(self):
        self.assertTrue(self.say("What was the biggest win of the season?").startswith("Boston Celtics 120-99"))
        self.assertTrue(self.say("What was the closest game of the season?").startswith("Denver Nuggets 102-101"))
        self.assertTrue(self.say("Who won on Christmas between the Celtics and the Nuggets?").startswith("The Denver Nuggets"))

    def test_team_ratings(self):
        possessions = 4 * (90 + 0.44 * 20 - 10 + 12)
        rating = 100 * (110 + 95 + 120 + 101) / possessions
        self.assertIn(f"{rating:.1f}", self.say("What is the Celtics' offensive rating?"))

    def test_reading(self):
        q = parse("Forwards under 25 on the Celtics with more than 20 points and 5 rebounds", None)
        self.assertEqual((q.roles, q.max_age, [t["full_name"] for t in q.roster], q.thresholds), (["Forward"], 24, ["Boston Celtics"], [("points", ">", 20), ("reb", ">", 5)]))
        self.assertEqual(parse("Who averaged over 10 points?", None).min_age, None)
        self.assertEqual(parse("Players with a net rating above 10", None).limits, [(">", 10)])
        self.assertIsNone(parse("Players with a net rating above 10", None).min_age)
        self.assertEqual(parse("Tatum against the Nuggets on the road", None).home, False)

    def test_sums(self):
        sums = sum_players(None, Query(""))
        self.assertEqual((sums.at[10, "points"], sums.at[10, "gp"], sums.at[20, "reb"]), (100, 4, 48))

    def test_follow_ups(self):
        first = "How many points does Jayson Tatum average?"
        self.assertEqual(standalone("What about Jokic?", first, None), "How many points does Nikola Jokić average?")
        self.assertEqual(standalone("How many rebounds does he average?", first, None), "How many rebounds does Jayson Tatum average?")
        self.assertIn("at home", standalone("And at home?", first, None))
        self.assertEqual(standalone("And at home?", "How many 30-point games did Tatum have?", None), "How many 30-point games did Tatum have at home?")
        self.assertIn("had 2 games", self.say("How many 30-point games did Tatum have at home?"))
        self.assertNotIn("tpm", [m.key for m in parse("How many 30-point games did Tatum have?", None).metrics])
        self.assertEqual([m.key for m in parse("Who made the most 3s?", None).metrics], ["tpm"])
        self.assertEqual(standalone("Best scorers in the league", first, None), "Best scorers in the league")
        self.assertIn("Jokić", standalone("Who is taller?", "Compare Tatum and Jokic", None))


if __name__ == "__main__":
    unittest.main()
