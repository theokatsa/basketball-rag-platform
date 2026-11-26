"""The StatQuery contract and the executor's checks that need no database."""

import unittest

from pydantic import ValidationError

from app.services.llm_reader import EXAMPLES, system_prompt
from app.services.query_executor import _condition_words, _same_person
from app.services.stat_query import STAT_KEYS, Condition, StatQuery, json_schema


class Contract(unittest.TestCase):
    def test_unknown_statistic_is_refused(self):
        with self.assertRaises(ValidationError):
            StatQuery.model_validate({"measure": {"stat": "fast_break_points", "basis": "per_game"}})

    def test_schema_requires_every_field(self):
        schema = json_schema()
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["conditions"]["items"]["properties"]["stat"]["enum"], STAT_KEYS)

    def test_examples_fit_the_contract(self):
        for question, answer in EXAMPLES:
            with self.subTest(question):
                StatQuery.model_validate_json(answer)
        self.assertIn("three_pct", system_prompt())

    def test_limit_is_bounded(self):
        with self.assertRaises(ValidationError):
            StatQuery.model_validate({"limit": 500})


class Names(unittest.TestCase):
    def test_a_first_name_is_not_enough(self):
        self.assertFalse(_same_person("Michael Jordan", "Michael Porter Jr."))

    def test_accents_suffixes_and_aliases(self):
        self.assertTrue(_same_person("Luka Doncic", "Luka Dončić"))
        self.assertTrue(_same_person("Jokic", "Nikola Jokić"))
        self.assertTrue(_same_person("Jimmy Butler", "Jimmy Butler III"))
        self.assertTrue(_same_person("SGA", "Shai Gilgeous-Alexander"))


class Words(unittest.TestCase):
    def test_conditions_read_as_sentences(self):
        self.assertEqual(_condition_words(Condition(stat="games", basis="total", op=">=", value=50), "player"), "at least 50 games played")
        self.assertEqual(_condition_words(Condition(stat="points", basis="in_game", op=">=", value=40), "player"), "at least 40 points in the game")
        self.assertEqual(_condition_words(Condition(stat="triple_doubles", basis="in_game", op=">=", value=1), "player"), "a triple-double")


if __name__ == "__main__":
    unittest.main()
