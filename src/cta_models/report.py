"""A self-contained HTML summary and machine-readable research outputs."""

from html import escape
from pathlib import Path

import pandas as pd

from .config import MARKETS
from .model import Snapshot
from .scenarios import scenario_table, trigger_levels


def _plot(values: pd.Series, color: str) -> str:
    series = values.dropna().tail(500)
    if series.empty:
        return ""
    low, high = float(series.min()), float(series.max())
    spread = max(high - low, 1e-9)
    coords = " ".join(f"{i * 700 / max(len(series)-1,1):.1f},{160-(v-low)*140/spread:.1f}"
                      for i, v in enumerate(series.to_numpy()))
    return f'<svg viewBox="0 0 700 180" role="img" aria-label="Recent history"><polyline fill="none" stroke="{color}" stroke-width="2" points="{coords}"/></svg>'


def write_report(results: dict[str, tuple[pd.DataFrame, Snapshot]], out_dir: str | Path) -> Path:
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    summaries, scenarios, panels = [], [], []
    for market, (positions, snapshot) in results.items():
        latest = positions.iloc[-1]
        base, components = snapshot.at_price(snapshot.raw_price)
        if abs(base - latest["exposure"]) > 1e-9:
            raise ValueError("Scenario engine disagrees with latest historical position")
        triggers = trigger_levels(snapshot)
        summary = {"market": market, "as_of": latest["date"].date().isoformat(),
                   "price": snapshot.raw_price, "price_unit": MARKETS[market].price_unit,
                   "model_exposure_pct": base * 100,
                   "historical_percentile": float(latest["exposure_percentile"]),
                   "annualized_volatility_pct": float(latest["volatility"] * 100),
                   "risk_scale_pct": float(latest["risk_scale"] * 100),
                   **{f"signal_{h}_pct": components[h] * 100 for h in snapshot.config.horizons},
                   **triggers, "data_source": str(latest["source"])}
        summaries.append(summary)
        table = scenario_table(snapshot)
        scenarios.append(table)
        positions.to_csv(dest / f"{market.lower()}_positions.csv", index=False, float_format="%.8f")
        panels.append(f"<h2>{escape(market)} · {escape(summary['as_of'])}</h2>"
                      f"<p>Quote: {snapshot.raw_price:,.2f} {escape(MARKETS[market].price_unit)} · "
                      f"Model exposure: <strong>{base*100:+.1f}%</strong> · "
                      f"Historical signed percentile: {summary['historical_percentile']:.0f}th · "
                      f"Risk scale: {summary['risk_scale_pct']:.0f}%</p>"
                      f"<p>Medium and long components carry 75% of the ensemble weight. "
                      f"Volatility is held fixed in the conditional scenarios. "
                      f"10 percentage-point sell trigger: {triggers['sell_10pp'] or 'outside range'}</p>"
                      f"<h3>Recent model exposure</h3>{_plot(positions['exposure']*100, '#2980b9')}"
                      f"<h3>Price scenarios</h3>{table[['price_change_pct','scenario_price','exposure_pct','change_pp']].round(2).to_html(index=False, border=0)}")
    pd.DataFrame(summaries).to_csv(dest / "summary.csv", index=False, float_format="%.8f")
    pd.concat(scenarios, ignore_index=True).to_csv(dest / "scenarios.csv", index=False, float_format="%.8f")
    synthetic = any(str(item["data_source"]).startswith("SYNTHETIC") for item in summaries)
    banner = ("SYNTHETIC DEMONSTRATION — invented prices; no inference about historical or current CTA positions."
              if synthetic else "MODEL ESTIMATE — not observed CTA holdings. Verify source timing and roll construction.")
    html = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Metals CTA model</title>"
            "<style>body{font:16px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;color:#17212b}"
            "header{background:#fff1ca;padding:1rem}table{border-collapse:collapse;width:100%}"
            "th,td{text-align:right;padding:.5rem;border-bottom:1px solid #ddd}svg{width:100%;background:#f7f9fb}</style>"
            f"<header><h1>Metals CTA positioning proxy</h1><strong>{escape(banner)}</strong>"
            "<p>−100% to +100% means model exposure relative to its own risk limit. It is not a count of actual CTA contracts.</p></header>"
            + "".join(panels) + "</html>")
    path = dest / "report.html"
    path.write_text(html, encoding="utf-8")
    return path

