"""Display sampling must retain observations without changing model calculations."""

import unittest

import pandas as pd

from cta_models.charting import weekly_last_session


class WeeklyChartTests(unittest.TestCase):
    def test_last_observed_session_and_partial_week(self):
        daily = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-28", "2026-10-01", "2026-10-02",
                                    "2026-10-05", "2026-10-07", "2026-10-08"]),
            "exposure": [10, 11, 12, 13, 14, 15],
            "rsi14": [40, 41, 42, 43, 44, 45],
        })
        result = weekly_last_session(daily)
        self.assertEqual(result["date"].dt.strftime("%Y-%m-%d").tolist(), ["2026-10-02", "2026-10-08"])
        self.assertEqual(result["exposure"].tolist(), [12, 15])
        self.assertEqual(result["rsi14"].tolist(), [42, 45])
        self.assertEqual(len(daily), 6)
        self.assertTrue(weekly_last_session(daily.iloc[:0]).empty)


if __name__ == "__main__":
    unittest.main()
