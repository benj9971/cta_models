"""Render provisional CTA positioning charts from labelled research proxies.

Run after fetching the three proxy CSVs. No futures backtest or executable
position is inferred from the vendor's unverified continuous-contract series.
"""

import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cta_models.data import load_csv
from cta_models.charting import weekly_last_session
from cta_models.indicators import rsi
from cta_models.model import compute_positions

METALS = {
    "COMEX_HG": ("COMEX copper", "US cents/lb", "#ad6b29"),
    "NYMEX_PL": ("NYMEX platinum", "USD/troy oz", "#596bb1"),
    "NYMEX_PA": ("NYMEX palladium", "USD/troy oz", "#7a5aa6"),
    "COMEX_GC": ("COMEX gold", "USD/troy oz", "#b99a45"),
    "COMEX_SI": ("COMEX silver", "USD/troy oz", "#778792"),
    "SGX_IO62": ("Iron ore · CME proxy for SGX", "USD/dmt", "#567d59"),
    "LME_CU": ("LME copper 3M", "USD/t", "#b5651d"),
    "LME_AL": ("LME aluminium 3M", "USD/t", "#8a9aa8"),
    "LME_NI": ("LME nickel 3M", "USD/t", "#5f7f6a"),
    "LME_ZN": ("LME zinc 3M", "USD/t", "#6f86a0"),
    "LME_PB": ("LME lead 3M", "USD/t", "#5c5c6e"),
}


def price_file(data_dir, market):
    """LME series come from update_lme_3m.py; the rest from the Yahoo proxy fetcher."""
    if market.startswith("LME_"):
        return data_dir / f"{market.lower()}_westmetall_3m.csv"
    return data_dir / f"{market.lower()}_yahoo_research_proxy.csv"


def plot(market, prices, positions, path, years=None, frequency="Daily"):
    if frequency not in {"Daily", "Weekly"}:
        raise ValueError("Chart frequency must be Daily or Weekly")
    title, unit, color = METALS[market]
    valid = positions.dropna(subset=["exposure"])
    if years:
        valid = valid[valid["date"] >= valid["date"].iloc[-1] - pd.DateOffset(years=years)]
    if frequency == "Weekly":
        valid = weekly_last_session(valid)
    aligned = prices.set_index("date").loc[valid["date"]]
    exposure = valid["exposure"].to_numpy() * 100
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(12.8, 7.2), sharex=True,
                                    gridspec_kw={"height_ratios": [1, 1.35], "hspace": .12})
    fig.patch.set_facecolor("#f6f8fa")
    for ax in (top, bottom):
        ax.set_facecolor("white")
        ax.grid(axis="y", color="#e2e8ee")
        ax.spines[["top", "right"]].set_visible(False)
    top.plot(valid["date"], aligned["close"], color="#526878", lw=1.2)
    top.set_ylabel(f"Proxy quote · {unit}")
    bottom.axhline(0, color="#576675", lw=.8)
    bottom.plot(valid["date"], exposure, color=color, lw=1.5)
    bottom.fill_between(valid["date"], exposure, 0, color=color, alpha=.18)
    bottom.set_ylim(-105, 105)
    bottom.set_yticks([-100, -50, 0, 50, 100])
    bottom.set_ylabel("Model exposure · −100 to +100")
    bottom.xaxis.set_major_locator(mdates.YearLocator(1 if years else 3))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(f"{title} · CTA-style position proxy · {'Last 3 years' if years else 'Full model history'} · {frequency.lower()} display",
                 x=.07, y=.985, ha="left", fontsize=17, fontweight="bold")
    fig.text(.07, .925, f"{valid['date'].iloc[0].date()} to {valid['date'].iloc[-1].date()}   ·   "
             f"Latest position {exposure[-1]:+.1f}   ·   Quote {aligned['close'].iloc[-1]:,.2f} {unit}", fontsize=10)
    fig.text(.07, .025, ("Westmetall-published LME three-month quote (rolling prompt, not a closing price). "
             if market.startswith("LME_") else
             "Daily vendor continuous futures quote; contract mapping and roll adjustment unverified. ")
             + ("Iron ore is CME TIO, not SGX FEF.\n" if market == "SGX_IO62" else "\n") +
             "Signal-only research proxy; not observed CTA holdings or an executable futures backtest.",
             fontsize=9, color="#506171")
    fig.subplots_adjust(left=.075, right=.98, top=.875, bottom=.145)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("dashboard/data"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--markets", nargs="+", choices=METALS,
                        default=[m for m in METALS if not m.startswith("LME_")])
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip PNG rendering (scheduled watches need only the printed scores)")
    parser.add_argument("--full-frequency", choices=["Weekly", "Daily"], default="Weekly",
                        help="Chart display only; daily model calculations and CSVs are unchanged")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for market in args.markets:
        prices = load_csv(price_file(args.data_dir, market), market)
        positions = compute_positions(prices)
        out = args.output_dir / f"{market.lower()}_proxy_positions.csv"
        positions.to_csv(out, index=False)
        latest = positions.iloc[-1]
        print(market, len(prices), str(latest["date"].date()),
              "exposure", round(float(latest["exposure"])*100, 2),
              "RSI14", round(float(rsi(prices["close"]).iloc[-1]), 2),
              "components", {h: round(float(latest[f"signal_{h}"])*100, 2) for h in (20, 60, 120, 252)},
              flush=True)
        if args.no_charts:
            continue
        for suffix, years in (("full", None), ("3y", 3)):
            plot(market, prices, positions, args.output_dir / f"{market.lower()}_proxy_{suffix}.png", years,
                 args.full_frequency if years is None else "Daily")


if __name__ == "__main__":
    main()
