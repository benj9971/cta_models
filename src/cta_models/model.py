"""Transparent trend ensemble and bounded, volatility-scaled exposure."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import ModelConfig
from .data import validate_prices


def _component(price: pd.Series, horizon: int, daily_vol: pd.Series) -> pd.Series:
    # Both reference price and breakout range predate the current observation.
    past = price.shift(horizon)
    low = price.shift(1).rolling(horizon, min_periods=horizon).min()
    high = price.shift(1).rolling(horizon, min_periods=horizon).max()
    z = np.log(price / past) / (daily_vol * np.sqrt(horizon))
    momentum = np.tanh(z / 2)
    half_width = ((high - low) / 2).clip(lower=1e-9)
    breakout = ((price - (high + low) / 2) / half_width).clip(-1, 1)
    return (.5 * momentum + .5 * breakout).clip(-1, 1)


def compute_positions(prices: pd.DataFrame, config: ModelConfig = ModelConfig()) -> pd.DataFrame:
    data = validate_prices(prices)
    if len(data) <= max(config.horizons):
        raise ValueError(f"Need more than {max(config.horizons)} dated observations")
    result = data[["date", "market", "contract", "close", "signal_close", "source"]].copy()
    price = data["signal_close"]
    log_returns = np.log(price / price.shift(1))
    daily_vol = log_returns.rolling(config.volatility_lookback,
                                    min_periods=config.volatility_lookback).std(ddof=1)
    daily_vol = daily_vol.clip(lower=config.volatility_floor / np.sqrt(config.annualization))
    result["volatility"] = daily_vol * np.sqrt(config.annualization)
    for horizon in config.horizons:
        result[f"signal_{horizon}"] = _component(price, horizon, daily_vol)
    columns = [f"signal_{h}" for h in config.horizons]
    result["raw_ensemble"] = result[columns].mul(config.weights).sum(axis=1, min_count=len(columns))
    result["risk_scale"] = (config.volatility_target / result["volatility"]).clip(upper=1)
    result["exposure"] = (result["raw_ensemble"] * result["risk_scale"]).clip(-1, 1)
    # Signed expanding percentile is descriptive; it uses no later observations.
    values = result["exposure"].to_numpy()
    percentile = np.full(len(values), np.nan)
    valid = []
    for i, value in enumerate(values):
        if np.isfinite(value):
            valid.append(value)
            if len(valid) >= 60:
                percentile[i] = 100 * np.mean(np.asarray(valid) <= value)
    result["exposure_percentile"] = percentile
    return result


@dataclass(frozen=True)
class Snapshot:
    market: str
    as_of: pd.Timestamp
    reference_price: float
    raw_price: float
    daily_vol: float
    risk_scale: float
    history: dict[int, tuple[float, float, float]]  # prior-n price, prior-n low, prior-n high
    config: ModelConfig

    def at_price(self, raw_price: float) -> tuple[float, dict[int, float]]:
        """Hypothetical last price with historical references and volatility held fixed."""
        if raw_price <= 0:
            raise ValueError("Scenario price must be positive")
        adjusted = self.reference_price + raw_price - self.raw_price
        if adjusted <= 0:
            raise ValueError("Scenario implies a nonpositive adjusted price")
        components = {}
        for horizon, (past, low, high) in self.history.items():
            z = np.log(adjusted / past) / (self.daily_vol * np.sqrt(horizon))
            breakout = np.clip((adjusted - (high + low) / 2) / max((high - low) / 2, 1e-9), -1, 1)
            components[horizon] = float(np.clip(.5 * np.tanh(z / 2) + .5 * breakout, -1, 1))
        ensemble = sum(weight * components[h] for h, weight in
                       zip(self.config.horizons, self.config.weights))
        return float(np.clip(ensemble * self.risk_scale, -1, 1)), components


def make_snapshot(prices: pd.DataFrame, positions: pd.DataFrame,
                  config: ModelConfig = ModelConfig()) -> Snapshot:
    data = validate_prices(prices)
    if not data["date"].equals(positions["date"]):
        raise ValueError("Positions must correspond to the same dated price series")
    last = positions.iloc[-1]
    if not np.isfinite(last["exposure"]):
        raise ValueError("Latest observation does not have a complete model history")
    price = data["signal_close"].to_numpy()
    history = {}
    for horizon in config.horizons:
        preceding = price[-1-horizon:-1]
        history[horizon] = (float(price[-1-horizon]), float(preceding.min()), float(preceding.max()))
    return Snapshot(str(last["market"]), last["date"], float(price[-1]), float(last["close"]),
                    float(last["volatility"]) / np.sqrt(config.annualization),
                    float(last["risk_scale"]), history, config)
