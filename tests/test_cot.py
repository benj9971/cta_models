import unittest

import pandas as pd

from cta_models.config import MARKETS
from cta_models.cot import normalize
from cta_models.indicators import rsi


class PositioningDataTests(unittest.TestCase):
    def test_rsi_uses_close_sequence_without_lookahead(self):
        rising = pd.Series(range(1, 40), dtype=float)
        self.assertTrue(rsi(rising).iloc[:14].isna().all())
        self.assertEqual(rsi(rising).iloc[-1], 100.0)
        falling = pd.Series(range(40, 1, -1), dtype=float)
        self.assertEqual(rsi(falling).iloc[-1], 0.0)
        self.assertEqual(rsi(pd.Series([10.0] * 40)).iloc[-1], 50.0)
        revised = rising.copy()
        revised.iloc[-1] = 100.0
        self.assertEqual(rsi(rising).iloc[-2], rsi(revised).iloc[-2])

    def test_contract_metadata_and_cot_normalization(self):
        self.assertAlmostEqual(MARKETS["COMEX_HG"].contract_size_tonnes, 11.33980925)
        self.assertEqual(MARKETS["NYMEX_PL"].contract_size, 50)
        self.assertEqual(MARKETS["COMEX_GC"].contract_size, 100)
        self.assertEqual(MARKETS["COMEX_SI"].contract_size, 5000)
        self.assertIsNone(MARKETS["NYMEX_PL"].contract_size_tonnes)
        self.assertIsNone(MARKETS["SGX_IO62"].contract_size)
        row = {
            "report_date_as_yyyy_mm_dd": "2026-09-29T00:00:00.000",
            "cftc_contract_market_code": "085692",
            "market_and_exchange_names": "COPPER - COMEX",
            "open_interest_all": "300000",
            "m_money_positions_long_all": "92000",
            "m_money_positions_short_all": "14000",
            "m_money_positions_spread": "35000",
        }
        result = normalize([row], "2026-10-09T06:00:00+00:00")[0]
        self.assertEqual(result["managed_money_net"], 78000)
        self.assertEqual(result["managed_money_net_pct_oi"], 0.26)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            normalize([row, row], "2026-10-09T06:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
