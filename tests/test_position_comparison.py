"""Check the key timing and reconciliation risks on bundled research histories."""

import unittest

import numpy as np

from scripts.compare_reported_positions import DATA, MARKETS, build


class ReportComparisonTests(unittest.TestCase):
    def test_report_join_never_uses_later_quote(self):
        for market in MARKETS:
            with self.subTest(market=market):
                _, _, weekly = build(market, DATA)
                matched = weekly.dropna(subset=["model_score"])
                self.assertGreater(len(matched), 100)
                age = (matched["position_date"] - matched["price_date"]).dt.days
                self.assertTrue(age.between(0, 7).all())
                self.assertTrue(np.allclose(matched["reported_long"] - matched["reported_short"],
                                            matched["reported_net"], atol=.02))
                self.assertTrue(matched["model_score"].between(-100, 100).all())
        _, _, nickel = build("LME_NI", DATA)
        missing = nickel.loc[nickel["price_date"].isna(), "position_date"].dt.strftime("%Y-%m-%d").tolist()
        self.assertEqual(missing, ["2022-03-18", "2022-03-25"])


if __name__ == "__main__":
    unittest.main()
