"""Conditional positioning changes, not forecasts of actual CTA orders."""

import numpy as np
import pandas as pd

from .model import Snapshot

SHOCKS = (-.10, -.05, -.03, -.01, 0, .01, .03, .05, .10)


def scenario_table(snapshot: Snapshot, shocks: tuple[float, ...] = SHOCKS) -> pd.DataFrame:
    base, _ = snapshot.at_price(snapshot.raw_price)
    rows = []
    for shock in shocks:
        price = snapshot.raw_price * (1 + shock)
        exposure, components = snapshot.at_price(price)
        rows.append({"market": snapshot.market, "as_of": snapshot.as_of,
                     "price_change_pct": shock * 100, "scenario_price": price,
                     "exposure_pct": exposure * 100,
                     "change_pp": (exposure - base) * 100,
                     **{f"signal_{h}_pct": value * 100 for h, value in components.items()}})
    return pd.DataFrame(rows)


def trigger_levels(snapshot: Snapshot, span: float = .25, steps: int = 1001) -> dict[str, float | None]:
    """Nearest levels for ensemble direction or a 10-point exposure change.

    Volatility is fixed at today's observed estimate. A level outside +/-span
    is reported as unavailable, never extrapolated.
    """
    base, _ = snapshot.at_price(snapshot.raw_price)
    grid = snapshot.raw_price * (1 + np.linspace(-span, span, steps))
    exposure = np.array([snapshot.at_price(float(p))[0] for p in grid])

    def closest_crossing(target: float, side: str) -> float | None:
        indices = np.where(np.diff(np.sign(exposure - target)) != 0)[0]
        candidates = [(grid[i] + grid[i + 1]) / 2 for i in indices]
        candidates = [p for p in candidates if (p < snapshot.raw_price if side == "down" else p > snapshot.raw_price)]
        return float(min(candidates, key=lambda p: abs(p - snapshot.raw_price))) if candidates else None

    return {"direction_flip_down": closest_crossing(0, "down") if base > 0 else None,
            "direction_flip_up": closest_crossing(0, "up") if base < 0 else None,
            "sell_10pp": closest_crossing(base - .10, "down"),
            "buy_10pp": closest_crossing(base + .10, "up")}
