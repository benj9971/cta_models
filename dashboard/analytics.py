"""Research analytics isolated from the existing signal engine and Streamlit."""

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pandas as pd

from cta_models.data import validate_prices
from cta_models.model import Snapshot, compute_positions, make_snapshot
from cta_models.synthetic import copper_pair


@dataclass
class Run:
    prices: pd.DataFrame
    positions: pd.DataFrame
    snapshot: Snapshot
    synthetic: bool
    loaded_at: pd.Timestamp


def build_run(market: str, payload: bytes | None = None) -> Run:
    prices = copper_pair()[market] if payload is None else pd.read_csv(BytesIO(payload))
    if prices.empty:
        raise ValueError("The CSV has no price rows")
    prices = validate_prices(prices, market)
    # Uploaded files may themselves contain synthetic data. Inspect every row.
    synthetic = prices["source"].astype(str).str.upper().str.contains("SYNTHETIC", regex=False).any()
    positions = compute_positions(prices)
    return Run(prices, positions, make_snapshot(prices, positions), bool(synthetic),
               pd.Timestamp.now(tz="UTC"))


def diagnostics(run: Run) -> pd.DataFrame:
    prices, positions = run.prices, run.positions
    age = (pd.Timestamp.now(tz="UTC").date() - prices["date"].iloc[-1].date()).days
    gaps = prices["date"].diff().dt.days
    return pd.DataFrame([
        ("Data source", ", ".join(prices["source"].astype(str).unique())),
        ("Observations", str(len(prices))),
        ("Complete signal rows", str(positions["exposure"].notna().sum())),
        ("Warm-up rows", str(positions["exposure"].isna().sum())),
        ("First / last date", f"{prices['date'].iloc[0].date()} / {prices['date'].iloc[-1].date()}"),
        ("Calendar age (days)", str(age)),
        ("Date gaps > 4 calendar days", str((gaps > 4).sum())),
        ("Quote-label changes", str(prices["contract"].ne(prices["contract"].shift()).iloc[1:].sum())),
        ("Availability timestamps", "Present" if "available_at" in prices else "Absent"),
        ("Raw / adjusted quote", f"{run.snapshot.raw_price:,.4f} / {run.snapshot.reference_price:,.4f}"),
    ], columns=["Check", "Value"])


def backtest(run: Run, cost_bps: float = 2.0, return_basis: str = "signal_proxy",
             start=None, end=None) -> tuple[pd.DataFrame, dict[str, float]]:
    """Lagged exposure research test, not a futures account simulation.

    pnl_return, if supplied, is decimal daily return on unit notional exposure,
    ending at the row's date. Its roll and execution construction is external.
    Signal proxy returns can be distorted by additive adjustment. Never use
    raw changing-contract quote returns to infer performance.
    """
    if not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("Costs must be finite and nonnegative")
    if return_basis == "provided":
        if "pnl_return" not in run.prices:
            raise ValueError("Upload a pnl_return column to use supplied tradable returns")
        returns = pd.to_numeric(run.prices["pnl_return"], errors="raise")
        if not np.isfinite(returns).all() or (returns <= -1).any():
            raise ValueError("pnl_return must contain finite decimal returns greater than -1")
    elif return_basis == "signal_proxy":
        returns = run.prices["signal_close"].pct_change(fill_method=None)
    else:
        raise ValueError("Unknown return basis")
    data = run.positions[["date", "exposure"]].copy()
    # Today's close cannot set exposure for the return that just ended.
    data["held_exposure"] = data["exposure"].shift(1)
    data["market_return"] = returns
    data = data.dropna(subset=["held_exposure", "market_return"])
    if start is not None:
        data = data[data["date"] >= pd.Timestamp(start)]
    if end is not None:
        data = data[data["date"] <= pd.Timestamp(end)]
    data = data.reset_index(drop=True)
    if len(data) < 2:
        raise ValueError("Select at least two post-warm-up return observations")
    # Start each chosen evaluation window flat, charging the initial entry.
    previous = data["held_exposure"].shift(1, fill_value=0.0)
    data["turnover"] = (data["held_exposure"] - previous).abs()
    data["gross_return"] = data["held_exposure"] * data["market_return"]
    data["cost"] = data["turnover"] * cost_bps / 10_000
    data["net_return"] = data["gross_return"] - data["cost"]
    if (data["net_return"] <= -1).any():
        raise ValueError("Returns/costs exhaust the normalized capital; cannot compound")
    data["strategy_equity"] = (1 + data["net_return"]).cumprod()
    data["benchmark_equity"] = (1 + data["market_return"]).cumprod()
    # Include initial capital in the peak so first-day losses are drawdowns.
    data["drawdown"] = data["strategy_equity"] / data["strategy_equity"].cummax().clip(lower=1) - 1
    scale = run.snapshot.config.annualization
    std = float(data["net_return"].std(ddof=1))
    metrics = {
        "Total return": float(data["strategy_equity"].iloc[-1] - 1),
        "Annualized return": float(data["strategy_equity"].iloc[-1] ** (scale / len(data)) - 1),
        "Annualized volatility": std * np.sqrt(scale),
        "Sharpe (zero cash rate)": float(data["net_return"].mean() / std * np.sqrt(scale)) if std > 0 else np.nan,
        "Max drawdown": float(data["drawdown"].min()),
        "Annualized turnover": float(data["turnover"].sum() / len(data) * scale),
        "Observations": float(len(data)),
    }
    return data, metrics


def component_table(run: Run) -> pd.DataFrame:
    config = run.snapshot.config
    latest = run.positions.iloc[-1]
    return pd.DataFrame([
        {"Horizon (sessions)": h, "Weight (%)": w * 100,
         "Signal (points)": latest[f"signal_{h}"] * 100,
         "Exposure contribution (points)": latest[f"signal_{h}"] * w * latest["risk_scale"] * 100}
        for h, w in zip(config.horizons, config.weights)
    ])
