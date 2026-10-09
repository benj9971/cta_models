"""Inputs distinguish quoted prices from signal histories.

The importer does not invent a continuous futures series from a changing
contract label. A source must supply a documented continuous signal_close.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from .config import MARKETS

REQUIRED = ("date", "market", "contract", "close", "signal_close", "source")
OHLC = ("open", "high", "low")


def validate_prices(frame: pd.DataFrame, expected_market: str | None = None) -> pd.DataFrame:
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    present_ohlc = set(OHLC) & set(frame.columns)
    if present_ohlc and present_ohlc != set(OHLC):
        raise ValueError("Supply all of open, high and low, or none of them")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    if data["date"].isna().any() or data["date"].duplicated().any():
        raise ValueError("Dates must be present and unique within one market")
    if data["market"].nunique() != 1 or data["market"].iloc[0] not in MARKETS:
        raise ValueError("Input must contain one configured market")
    if expected_market is not None and data["market"].iloc[0] != expected_market:
        raise ValueError(f"Expected {expected_market}")
    for column in ("contract", "source"):
        if data[column].isna().any() or (data[column].astype(str).str.strip() == "").any():
            raise ValueError(f"{column} must be populated")
    for column in (*present_ohlc, "close", "signal_close"):
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column]).all() or (data[column] <= 0).any():
            raise ValueError(f"{column} must contain finite positive prices")
    if present_ohlc and ((data["high"] < data[["open", "close", "low"]].max(axis=1)) |
                         (data["low"] > data[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC ranges are inconsistent")
    if "available_at" in data:
        timestamps = pd.to_datetime(data["available_at"], utc=True, errors="raise")
        if timestamps.isna().any() or (timestamps.dt.date < data["date"].dt.date).any():
            raise ValueError("available_at must follow its trade date")
        data["available_at"] = timestamps
    return data.sort_values("date").reset_index(drop=True)


def load_csv(path: str | Path, expected_market: str | None = None) -> pd.DataFrame:
    return validate_prices(pd.read_csv(path), expected_market)

