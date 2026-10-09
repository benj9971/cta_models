import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from dashboard.analytics import backtest, build_run, component_table
from cta_models.config import MARKETS


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

    def test_included_nickel_history_survives_market_disruption_gap(self):
        path = Path(__file__).resolve().parents[1] / "dashboard" / "data" / "lme_nickel_3m_westmetall_2008-2026_import.csv"
        run = build_run("LME_NI", path.read_bytes())
        self.assertEqual(MARKETS["LME_NI"].contract_size_tonnes, 6.0)
        self.assertEqual(len(run.prices), 4615)
        self.assertEqual(run.prices["date"].iloc[0], pd.Timestamp("2008-06-17"))
        self.assertEqual(run.prices["date"].iloc[-1], pd.Timestamp("2026-10-08"))
        self.assertEqual(run.positions["exposure"].notna().sum(), 4363)
        self.assertEqual(run.prices["date"].diff().dt.days.max(), 21)
        self.assertAlmostEqual(run.snapshot.at_price(run.snapshot.raw_price)[0],
                               run.positions["exposure"].iloc[-1])


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "optional Streamlit dependency absent")
class DashboardUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py"), default_timeout=30).run()

    def test_included_history_and_manual_load(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["run"].prices), 4743)
        self.assertFalse(app.session_state["run"].synthetic)
        self.assertEqual(str(app.session_state["run"].snapshot.as_of.date()), "2026-10-08")
        next(r for r in app.radio if "Synthetic demo" in r.options).set_value("Synthetic demo")
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
        loaded_at = app.session_state["run"].loaded_at
        next(r for r in app.radio if "Upload CSV" in r.options).set_value("Upload CSV")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["run"].loaded_at, loaded_at)

    def test_comex_custom_scenario_matches_engine(self):
        app = self.app()
        app.selectbox[0].select("COMEX_HG")
        next(r for r in app.radio if "Synthetic demo" in r.options).set_value("Synthetic demo")
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
        prices = app.session_state["run"].prices.iloc[:253]
        app.session_state["run"] = build_run("LME_CU", prices.to_csv(index=False).encode())
        next(r for r in app.radio if "Positioning" in r.options).set_value("Backtests").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)

    def test_load_nickel_history(self):
        app = self.app()
        app.selectbox[0].select("LME_NI")
        next(r for r in app.radio if "LME nickel history (2008–2026)" in r.options).set_value("LME nickel history (2008–2026)")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["run"].snapshot.market, "LME_NI")
        self.assertEqual(len(app.session_state["run"].prices), 4615)
        self.assertTrue(app.warning)

    def test_reported_comparison_for_four_metals_and_rsi(self):
        app = self.app()
        self.assertTrue(any(s.value == "RSI(14) · daily quote" for s in app.subheader))
        next(r for r in app.radio if "Reported comparison" in r.options).set_value("Reported comparison").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any(s.value == "Conditional price levels" for s in app.subheader))
        self.assertEqual(len(app.dataframe), 2)
        for market in ("NYMEX_PL", "LME_NI", "LME_AL", "LME_CU"):
            next(s for s in app.selectbox if s.label == "Comparison market").set_value(market).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
        next(r for r in app.radio if "Last 3 years" in r.options).set_value("Full history").run()
        self.assertFalse(app.exception)

    def test_bundled_continuous_proxy_blocks_backtest(self):
        app = self.app()
        app.selectbox[0].select("NYMEX_PL")
        next(r for r in app.radio if "NYMEX platinum Yahoo continuous proxy (2010–2026)" in r.options).set_value(
            "NYMEX platinum Yahoo continuous proxy (2010–2026)")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["run"].snapshot.market, "NYMEX_PL")
        next(r for r in app.radio if "Backtests" in r.options).set_value("Backtests").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Backtests are unavailable" in w.message for w in app.warning))


if __name__ == "__main__":
    unittest.main()
