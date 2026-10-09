import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from dashboard.analytics import backtest, build_run, component_table


class DashboardAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = build_run("LME_CU")

    def test_engine_and_contributions_agree(self):
        run = self.baseline
        total = component_table(run)["Exposure contribution (points)"].sum()
        self.assertAlmostEqual(total, run.positions["exposure"].iloc[-1] * 100)
        self.assertAlmostEqual(run.snapshot.at_price(run.snapshot.raw_price)[0], run.positions["exposure"].iloc[-1])

    def test_backtest_uses_lag_and_entry_cost(self):
        run = self.baseline
        data, _ = backtest(run, cost_bps=7)
        i = run.prices.index[run.prices["date"] == data["date"].iloc[0]][0]
        exposure = run.positions["exposure"].iloc[i - 1]
        price_return = run.prices["signal_close"].iloc[i] / run.prices["signal_close"].iloc[i - 1] - 1
        self.assertAlmostEqual(data["gross_return"].iloc[0], exposure * price_return)
        self.assertAlmostEqual(data["cost"].iloc[0], abs(exposure) * 7 / 10_000)
        cropped, _ = backtest(run, 7, start=data["date"].iloc[10])
        self.assertAlmostEqual(cropped["turnover"].iloc[0], abs(cropped["held_exposure"].iloc[0]))

    def test_supplied_returns_and_initial_drawdown(self):
        run = build_run("LME_CU")
        run.prices["pnl_return"] = 0.0
        data, metrics = backtest(run, cost_bps=100, return_basis="provided")
        self.assertLess(data["drawdown"].iloc[0], 0)
        self.assertLess(metrics["Total return"], 0)
        np.testing.assert_allclose(data["gross_return"], 0)
        run.prices.loc[10, "pnl_return"] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            backtest(run, return_basis="provided")

    def test_bad_inputs_and_synthetic_upload(self):
        with self.assertRaisesRegex(ValueError, "no price rows"):
            build_run("LME_CU", b"date,market\n")
        with self.assertRaisesRegex(ValueError, "Expected"):
            build_run("COMEX_HG", self.baseline.prices.to_csv(index=False).encode())
        self.assertTrue(build_run("LME_CU", self.baseline.prices.to_csv(index=False).encode()).synthetic)
        with self.assertRaisesRegex(ValueError, "Costs"):
            backtest(self.baseline, cost_bps=-1)
        with self.assertRaisesRegex(ValueError, "pnl_return"):
            backtest(self.baseline, return_basis="provided")

    def test_future_price_change_does_not_change_past_performance(self):
        run = build_run("LME_CU")
        run.prices["pnl_return"] = run.prices["signal_close"].pct_change().fillna(0)
        original, _ = backtest(run, return_basis="provided")
        changed = run.prices.copy()
        changed.loc[len(changed) - 1, ["close", "signal_close", "high"]] *= 1.1
        other = build_run("LME_CU", changed.to_csv(index=False).encode())
        after, _ = backtest(other, return_basis="provided")
        pd.testing.assert_frame_equal(original.drop(columns="exposure"), after.drop(columns="exposure"))


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "optional Streamlit dependency absent")
class DashboardUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py"), default_timeout=30).run()

    def test_manual_load_and_views(self):
        app = self.app()
        self.assertNotIn("run", app.session_state)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["run"].synthetic)
        loaded_at = app.session_state["run"].loaded_at
        app.selectbox[0].select("COMEX_HG").run()
        self.assertEqual(app.session_state["run"].snapshot.market, "LME_CU")
        self.assertEqual(app.session_state["run"].loaded_at, loaded_at)
        view = next(r for r in app.radio if "Positioning" in r.options)
        for name in ("Price scenarios", "Diagnostics", "Backtests"):
            next(r for r in app.radio if "Positioning" in r.options).set_value(name).run()
            self.assertFalse(app.exception)
        app.checkbox[0].check()
        next(b for b in app.button if b.label == "Run backtest").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(m.label == "Total return" for m in app.metric))

    def test_failed_load_preserves_previous_run(self):
        app = self.app()
        app.button[0].click().run()
        loaded_at = app.session_state["run"].loaded_at
        next(r for r in app.radio if "Upload CSV" in r.options).set_value("Upload CSV")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["run"].loaded_at, loaded_at)

    def test_comex_custom_scenario_matches_engine(self):
        app = self.app()
        app.selectbox[0].select("COMEX_HG")
        app.button[0].click().run()
        self.assertEqual(app.session_state["run"].snapshot.market, "COMEX_HG")
        next(r for r in app.radio if "Positioning" in r.options).set_value("Price scenarios").run()
        next(b for b in app.button if b.label == "Evaluate price").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        value = app.session_state["run"].positions["exposure"].iloc[-1] * 100
        self.assertEqual(app.metric[0].value, f"{value:+.1f}")

    def test_short_history_backtest_is_graceful(self):
        app = self.app()
        app.button[0].click().run()
        prices = app.session_state["run"].prices.iloc[:253]
        app.session_state["run"] = build_run("LME_CU", prices.to_csv(index=False).encode())
        next(r for r in app.radio if "Positioning" in r.options).set_value("Backtests").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)


if __name__ == "__main__":
    unittest.main()
