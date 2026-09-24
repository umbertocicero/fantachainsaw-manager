import unittest

from webapp import stats_engine


class TestValueCriterion(unittest.TestCase):
    def test_excellent_players_outscore_cheap_midtable_ones(self):
        strong = stats_engine.compute_player_value(
            fantamedia_corretta=7.8,
            gol=2,
            assist=1,
            qta=9,
            partite_valutate=12,
        )
        cheap = stats_engine.compute_player_value(
            fantamedia_corretta=6.4,
            gol=0,
            assist=0,
            qta=2,
            partite_valutate=12,
        )

        self.assertGreater(strong, cheap)


if __name__ == "__main__":
    unittest.main()
