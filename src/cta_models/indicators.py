"""Close-only technical indicators for separate research signals."""

import numpy as np
import pandas as pd


def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI (0–100), using a sequence of daily prices and no OHLC bars.

    The first ``period`` observations are warm-up; a perfectly flat market is
    defined as 50. RSI alone is not an inferred CTA position.
    """
    if period < 2:
        raise ValueError("period must be at least 2")
    values = pd.to_numeric(prices, errors="raise").astype(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("prices must be finite and positive")
    result = pd.Series(np.nan, index=prices.index, dtype=float, name="rsi")
    if len(values) <= period:
        return result
    delta = values.diff().to_numpy()
    gains = np.maximum(delta, 0.0)
    losses = np.maximum(-delta, 0.0)
    avg_gain = gains[1:period + 1].mean()
    avg_loss = losses[1:period + 1].mean()
    for idx in range(period, len(values)):
        if idx > period:
            avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
            avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
        if avg_loss == 0:
            value = 50.0 if avg_gain == 0 else 100.0
        elif avg_gain == 0:
            value = 0.0
        else:
            value = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        result.iloc[idx] = value
    return result
