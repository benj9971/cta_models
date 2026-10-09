"""Reproducible illustrative markets. Never treat outputs as historical data."""

import numpy as np
import pandas as pd

from .data import validate_prices


def copper_pair(start: str = "2018-01-02", periods: int = 2100, seed: int = 42) -> dict[str, pd.DataFrame]:
    if periods < 300:
        raise ValueError("At least 300 sessions are needed for long lookbacks")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=periods)
    common = rng.normal(size=periods)
    # Prescribed regimes exercise both trend and volatility controls.
    drift = np.select([np.arange(periods) < periods * .30,
                       np.arange(periods) < periods * .55,
                       np.arange(periods) < periods * .78],
                      [.0006, -.0005, .0], default=.0004)
    vol = np.where((np.arange(periods) > periods * .54) &
                   (np.arange(periods) < periods * .69), .025, .012)
    lme_signal = 8000.0 * np.exp(np.cumsum(drift + vol * common))
    # A mean-reverting basis keeps the two listings tied to the same copper
    # price while allowing daily exchange-specific noise.
    basis = np.zeros(periods)
    innovations = rng.normal(0, .002, periods)
    for i in range(1, periods):
        basis[i] = .93 * basis[i - 1] + innovations[i]
    outputs = {}
    for market, signal in (("LME_CU", lme_signal),
                           ("COMEX_HG", lme_signal / 22.0462262 * np.exp(basis))):
        # An illustrative monthly contract premium changes at a COMEX switch.
        premium = (1.5 + np.arange(periods) % 21 / 21) if market == "COMEX_HG" else np.zeros(periods)
        close = signal + premium
        open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, .004, periods))
        width = close * (np.abs(rng.normal(.006, .004, periods)) + .001)
        high = np.maximum(open_, close) + width
        low = np.maximum(.01, np.minimum(open_, close) - width)
        contract = (dates + pd.offsets.MonthBegin(1)).strftime("%Y-%m") if market == "COMEX_HG" else (
            dates + pd.offsets.BDay(65)).strftime("%Y-%m-%d")
        outputs[market] = validate_prices(pd.DataFrame({
            "date": dates, "market": market, "contract": contract,
            "open": open_, "high": high, "low": low, "close": close,
            "signal_close": signal, "source": "SYNTHETIC_NOT_HISTORICAL",
        }))
    return outputs
