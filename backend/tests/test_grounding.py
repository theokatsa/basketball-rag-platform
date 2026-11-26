import unittest

from app.services.grounding import check

SOURCE = ["Nikola Jokić played 70 games in 2024-25. Averages: 29.6 points, 12.7 rebounds. 57.6% from the field. 1,464 shots."]


class Grounding(unittest.TestCase):
    def test_supported(self):
        result = check("Jokić averaged 29.6 points [1].", "How is Jokic?", SOURCE)
        self.assertTrue(result["grounded"])
        self.assertEqual(result["cited"], [1])

    def test_rounding_is_allowed_but_changing_is_not(self):
        self.assertTrue(check("About 30 points [1].", "?", SOURCE)["grounded"])
        self.assertEqual(check("He averaged 29.8 points [1].", "?", SOURCE)["unsupported_numbers"], ["29.8"])

    def test_adding_precision_is_not_support(self):
        self.assertEqual(check("70.4 games [1]", "?", SOURCE)["unsupported_numbers"], ["70.4"])

    def test_numbers_from_the_question_and_lists_and_seasons(self):
        self.assertTrue(check("1. Jokić has more than 10 rebounds in 2024-25 [1]\n2. Nobody else.", "more than 10 rebounds?", SOURCE)["grounded"])

    def test_thousands(self):
        self.assertTrue(check("1464 shots [1]", "?", SOURCE)["grounded"])

    def test_invalid_citation(self):
        result = check("29.6 points [1, 4]", "?", SOURCE)
        self.assertEqual(result["invalid_citations"], [4])
        self.assertFalse(result["grounded"])


LIST = ["Shai Gilgeous-Alexander with 32.7 points per game, the highest. Next: Giannis Antetokounmpo 30.4, Nikola Jokić 29.6, Anthony Edwards 27.6."]
NAMES = ("Shai Gilgeous-Alexander", "Giannis Antetokounmpo", "Nikola Jokić", "Anthony Edwards", "Oklahoma City Thunder")


class Attribution(unittest.TestCase):
    def test_a_real_number_given_to_the_wrong_player(self):
        result = check("Jokic averaged 30.4 points [1].", "?", LIST, NAMES)
        self.assertEqual(result["unsupported_numbers"], [])  # the number exists, so the old check passed it
        self.assertEqual(result["misattributed"], ["30.4 (Nikola Jokić)"])
        self.assertFalse(result["grounded"])

    def test_the_right_owner_passes(self):
        self.assertTrue(check("Giannis Antetokounmpo is second with 30.4 [1], ahead of Jokić's 29.6.", "?", LIST, NAMES)["grounded"])

    def test_numbers_without_a_name_and_list_numbers_are_not_judged(self):
        self.assertTrue(check("1. Shai Gilgeous-Alexander 32.7\n2. Giannis Antetokounmpo 30.4 [1]", "?", LIST, NAMES)["grounded"])
        self.assertTrue(check("The leader scored 32.7 points a game [1].", "?", LIST, NAMES)["grounded"])

    def test_without_names_nothing_changes(self):
        self.assertTrue(check("Jokic averaged 30.4 points [1].", "?", LIST)["grounded"])


if __name__ == "__main__":
    unittest.main()
