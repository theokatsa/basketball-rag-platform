import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.services import audience_models as am
from app.services import audience_service as audience
from app.services import league_data as data

# Two circles of three players, and player 6 whom everybody opens.
VISITS = np.array([[1, 1, 0, 0, 0, 0, 1], [1, 0, 1, 0, 0, 0, 1], [0, 1, 1, 0, 0, 0, 1], [0, 0, 0, 1, 1, 0, 1], [0, 0, 0, 1, 0, 1, 1], [0, 0, 0, 0, 1, 1, 1]] * 4, dtype=float)
FOLK = pd.DataFrame({"player_id": range(7), "full_name": [f"P{i}" for i in range(7)], "position": ["Guard"] * 4 + ["Center"] * 3, "gp": 60, "mpg": 30, "overall_score": [99, 90, 80, 70, 50, 40, 30]}).set_index("player_id", drop=False)


class Models(unittest.TestCase):
    def test_counts(self):
        c = am.counts(VISITS)
        self.assertEqual((c[0, 1], c[0, 3], c[0, 0]), (4, 0, 0))

    def test_own_circle_beats_the_popular_player(self):
        for name in ("cosine", "jaccard", "ppmi", "ease", "walk"):
            m = getattr(am, name)(VISITS)
            for a, b in ((0, 3), (1, 4), (4, 2)):
                friend = {0: 1, 1: 2, 4: 5}[a]
                self.assertGreater(m[a, friend], m[a, b], name)

    def test_popularity_ranks_the_hub_first(self):
        m = am.popularity(VISITS)
        self.assertEqual(int(m[0].argmax()), 6)

    def test_ease_matches_its_definition(self):
        b = am.ease(VISITS, 5.0)
        self.assertTrue(np.allclose(np.diag(b), 0))
        # Every column is the ridge regression on the other players.
        others = [i for i in range(7) if i != 2]
        x = VISITS[:, others]
        expected = np.linalg.solve(x.T @ x + 5.0 * np.eye(6), x.T @ VISITS[:, 2])
        self.assertTrue(np.allclose(b[others, 2], expected))

    def test_shrinking_mistrusts_rare_pairs(self):
        x = np.vstack([VISITS, [[0, 0, 0, 0, 0, 0, 0]]])
        self.assertLess(am.cosine(x, 8)[0, 1], am.cosine(x)[0, 1])


class Rankings(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(data, "people", lambda db: FOLK)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_most_viewed_with_the_place_before(self):
        series = {(7, 0): pd.Series({0: 9.0, 4: 5.0, 1: 2.0}), (14, 7): pd.Series({4: 8.0, 0: 3.0})}
        with patch.object(audience, "viewers", lambda db, newest=None, oldest=0: series[(newest, oldest)]):
            items = audience.most_viewed(None, 7)
            self.assertEqual([(i["player_id"], i["viewers"], i["previous"]) for i in items], [(0, 9, 2), (4, 5, 1), (1, 2, None)])
            self.assertEqual([i["player_id"] for i in audience.most_viewed(None, 7, "Center")], [4])

    def test_hidden_gems_are_good_and_unseen(self):
        with patch.object(audience, "viewers", lambda db, newest=None, oldest=0: pd.Series({0: 50.0, 1: 1.0, 2: 30.0, 3: 20.0, 4: 10.0, 5: 5.0})):
            items = audience.hidden_gems(None)
        self.assertEqual(items[0]["player_id"], 1)
        self.assertTrue(all(FOLK.at[i["player_id"], "overall_score"] >= audience.GEM_MIN_SCORE for i in items))

    def test_trending_needs_more_than_the_usual_share(self):
        rows = [{"player_id": 0, "recent": 20, "earlier": 100}, {"player_id": 1, "recent": 30, "earlier": 10}, {"player_id": 2, "recent": 4, "earlier": 0}]
        with patch.object(audience, "_recent", lambda key, load: rows):
            items = audience.trending(None)
        self.assertEqual([i["player_id"] for i in items], [1])  # 0 as usual, 2 too few


if __name__ == "__main__":
    unittest.main()
