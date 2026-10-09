import unittest

import numpy as np
import pandas as pd

from cta_models.config import ModelConfig
from cta_models.data import validate_prices
from cta_models.model import compute_positions, make_snapshot
from cta_models.scenarios import scenario_table, trigger_levels
from cta_models.synthetic import copper_pair


class CopperModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pair = copper_pair(periods=400, seed=7)

    def test_synthetic_reproducibility_and_ranges(self):
        same = copper_pair(periods=400, seed=7)
        for market in self.pair:
            pd.testing.assert_frame_equal(self.pair[market], same[market])
            validate_prices(self.pair[market])

    def test_no_future_price_changes_past_positions(self):
        prices = self.pair["LME_CU"]
        before = compute_positions(prices)
        changed = prices.copy()
        changed.loc[399, ["signal_close", "close", "high"]] *= 1.1
        after = compute_positions(changed)
        pd.testing.assert_series_equal(before["exposure"].iloc[:-1], after["exposure"].iloc[:-1])
        self.assertNotEqual(before["exposure"].iloc[-1], after["exposure"].iloc[-1])

    def test_raw_roll_jump_cannot_create_signal(self):
        prices = self.pair["COMEX_HG"].copy()
        original = compute_positions(prices)["exposure"]
        prices.loc[300:, "contract"] = "ROLLED"
        for column in ("open", "high", "low", "close"):
            prices.loc[300:, column] += 40.0
        changed = compute_positions(prices)["exposure"]
        pd.testing.assert_series_equal(original, changed)

    def test_snapshot_matches_history_and_sell_shock(self):
        prices = self.pair["LME_CU"]
        positions = compute_positions(prices)
        snapshot = make_snapshot(prices, positions)
        exposure, components = snapshot.at_price(snapshot.raw_price)
        self.assertAlmostEqual(exposure, positions["exposure"].iloc[-1])
        for horizon in components:
            self.assertAlmostEqual(components[horizon], positions[f"signal_{horizon}"].iloc[-1])
        table = scenario_table(snapshot)
        self.assertTrue(np.all(np.diff(table["exposure_pct"]) >= -1e-9))
        self.assertLessEqual(table.loc[table["price_change_pct"] == -5, "change_pp"].iloc[0], 0)
        trigger_levels(snapshot)

    def test_volatility_cap_without_leverage(self):
        result = compute_positions(self.pair["LME_CU"], ModelConfig(volatility_target=.01))
        self.assertLessEqual(result["risk_scale"].max(), 1)
        self.assertLess(result["risk_scale"].iloc[-1], 1)
        self.assertLessEqual(result["exposure"].abs().max(), 1)

    def test_rejects_inconsistent_ohlc(self):
        invalid = self.pair["LME_CU"].copy()
        invalid.loc[0, "low"] = invalid.loc[0, "high"] + 1
        with self.assertRaisesRegex(ValueError, "OHLC"):
            validate_prices(invalid)

    def test_accepts_complete_close_only_series(self):
        prices = self.pair["LME_CU"].drop(columns=["open", "high", "low"])
        validated = validate_prices(prices)
        self.assertEqual(len(compute_positions(validated)), 400)
        with self.assertRaisesRegex(ValueError, "all of open, high and low"):
            validate_prices(self.pair["LME_CU"].drop(columns=["high"]))


if __name__ == "__main__":
    unittest.main()

