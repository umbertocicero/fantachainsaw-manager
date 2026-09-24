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

    def test_recommendations_are_fifteen_per_role_in_three_tiers(self):
        players = [
            {"id": index, "ruolo": "D", "nome": f"D{index}", "valore": 100 - index}
            for index in range(1, 18)
        ]

        stats_engine.recommendation_by_role(players)

        ranked = [p for p in players if p.get("recommendation_rank")]
        self.assertEqual(len(ranked), 15)
        self.assertEqual([p["recommendation_tier"] for p in ranked[:5]], ["strong"] * 5)
        self.assertEqual([p["recommendation_tier"] for p in ranked[5:10]], ["medium"] * 5)
        self.assertEqual([p["recommendation_tier"] for p in ranked[10:]], ["recommended"] * 5)


if __name__ == "__main__":
    unittest.main()
