import unittest

from app.services.query_planner import make_plan

TEAMS = [
    {"nba_team_id": 1, "full_name": "Los Angeles Lakers", "city": "Los Angeles", "nickname": "Lakers"},
    {"nba_team_id": 2, "full_name": "LA Clippers", "city": "Los Angeles", "nickname": "Clippers"},
    {"nba_team_id": 3, "full_name": "Miami Heat", "city": "Miami", "nickname": "Heat"},
    {"nba_team_id": 4, "full_name": "Phoenix Suns", "city": "Phoenix", "nickname": "Suns"},
]
NAMES = [("Giannis Antetokounmpo", 30), ("Nikola Jokić", 29), ("Jaren Jackson Jr.", 22), ("Trae Young", 24), ("Stephen Curry", 24), ("Seth Curry", 6), ("LeBron James", 24), ("Bronny James", 2), ("Kevin Durant", 27), ("Shai Gilgeous-Alexander", 32)]
PEOPLE = [{"player_id": i, "full_name": n, "points": p} for i, (n, p) in enumerate(NAMES, 1)]


def plan(question):
    return make_plan(question, "2024-25", PEOPLE, TEAMS)


def names(p):
    return [x["full_name"] for x in p.players]


class Players(unittest.TestCase):
    def test_full_name_without_suffix_or_accent(self):
        self.assertEqual(names(plan("Tell me about Jaren Jackson")), ["Jaren Jackson Jr."])
        self.assertEqual(names(plan("Tell me about nikola jokic")), ["Nikola Jokić"])

    def test_shared_last_name_prefers_the_better_scorer(self):
        self.assertEqual(names(plan("How did Curry play this season?")), ["Stephen Curry"])

    def test_possessive_and_nickname(self):
        self.assertEqual(names(plan("What is Durant's scoring average?")), ["Kevin Durant"])
        self.assertEqual(names(plan("How good is SGA?")), ["Shai Gilgeous-Alexander"])

    def test_order_follows_the_question(self):
        self.assertEqual(names(plan("Compare LeBron James with Giannis Antetokounmpo")), ["LeBron James", "Giannis Antetokounmpo"])

    def test_trae_young_is_not_young_players(self):
        p = plan("How many points does Trae Young score?")
        self.assertEqual((names(p), p.max_age, p.intent), (["Trae Young"], None, "lookup"))


class Constraints(unittest.TestCase):
    def test_thresholds_inherit_the_comparison(self):
        self.assertEqual(plan("Players with more than 20 points and 7 rebounds").thresholds, [("points", ">", 20), ("rebounds", ">", 7)])

    def test_plus_and_or_more(self):
        self.assertEqual(plan("Anyone with 2+ blocks").thresholds, [("blocks", ">=", 2)])
        self.assertEqual(plan("Players with 8 or more assists").thresholds, [("assists", ">=", 8)])

    def test_percentages(self):
        self.assertEqual(plan("Players shooting at least 40% from three").thresholds, [("three_point_pct", ">=", 40)])
        self.assertEqual(plan("Who shoots over 90 percent on free throws?").thresholds, [("free_throw_pct", ">", 90)])

    def test_ages(self):
        p = plan("Players like Giannis under 25")
        self.assertEqual((p.intent, names(p), p.max_age), ("similar", ["Giannis Antetokounmpo"], 24))
        self.assertEqual(plan("Scorers over 35").min_age, 36)
        self.assertEqual(plan("Guards aged 20 to 23").min_age, 20)
        self.assertEqual(plan("Wings 22 or younger").max_age, 22)

    def test_a_threshold_is_not_an_age(self):
        p = plan("Guards who score over 25 points")
        self.assertEqual((p.min_age, p.thresholds, p.roles), (None, [("points", ">", 25)], ["Guard"]))

    def test_position_and_team(self):
        p = plan("Which centers on the Heat rebound well?")
        self.assertEqual((p.intent, p.roles, [t["full_name"] for t in p.teams], p.skills), ("ranking", ["Center"], ["Miami Heat"], ["rebounds"]))


class Intent(unittest.TestCase):
    def test_guards_as_a_verb(self):
        p = plan("Who guards LeBron James best?")
        self.assertEqual((p.intent, p.kinds, p.roles), ("lookup", ["matchups"], []))

    def test_lookups(self):
        for question, kind in [
            ("Best duo on the Lakers", "pairs"), ("Where does Kevin Durant shoot from?", "shot_profile"), ("Did the Suns beat the Heat?", "game"),
            ("How has Stephen Curry played lately?", "form"), ("How good are the Suns?", "team_season"), ("What is Nikola Jokic's assist average?", "player_season"),
        ]:
            self.assertEqual((plan(question).intent, plan(question).kinds), ("lookup", [kind]), question)

    def test_team_rankings(self):
        self.assertEqual(plan("Which team defends best?").order, ("def_rating", False))
        self.assertEqual(plan("Which team has the worst offense?").order, ("off_rating", False))
        self.assertEqual(plan("Which team commits the fewest turnovers?").order, ("turnovers", False))
        self.assertEqual(plan("Which team commits the most turnovers?").order, ("turnovers", True))

    def test_heat_the_word_is_not_a_team(self):
        self.assertEqual(plan("Who brings the heat from three?").teams, [])

    def test_out_of_scope(self):
        for question in ("Who led the league in 2010-11?", "What does LeBron James get paid?", "Who won the 2019 title?"):
            self.assertEqual(plan(question).intent, "out_of_scope", question)
        self.assertNotEqual(plan("Best scorers of 2024-25").intent, "out_of_scope")

    def test_open(self):
        self.assertEqual(plan("Something about basketball").intent, "open")


if __name__ == "__main__":
    unittest.main()
