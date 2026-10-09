"""Compare CTA-style model exposure to reported fund positioning, price and RSI.

Usage: python scripts/compare_reported_positions.py --output-dir output/position_comparison

Charts are descriptive and aligned to report *position dates*, not the later
release dates. Do not use the joined report values in a same-day trading test.
"""

import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cta_models.data import load_csv
from cta_models.charting import weekly_last_session
from cta_models.indicators import rsi
from cta_models.model import compute_positions, make_snapshot
from cta_models.scenarios import scenario_table, trigger_levels


DATA = Path(__file__).resolve().parents[1] / "dashboard" / "data"
MARKETS = {
    "NYMEX_PL": ("NYMEX platinum", "nymex_pl_yahoo_research_proxy.csv", "USD/troy oz", "#6176a9"),
    "COMEX_GC": ("COMEX gold", "comex_gc_yahoo_research_proxy.csv", "USD/troy oz", "#b99a45"),
    "COMEX_SI": ("COMEX silver", "comex_si_yahoo_research_proxy.csv", "USD/troy oz", "#778792"),
    "LME_NI": ("LME nickel", "lme_nickel_3m_westmetall_2008-2026_import.csv", "USD/t", "#8573a1"),
    "LME_AL": ("LME aluminium", "lme_aluminium_3m_westmetall_2008-2026_staged.csv", "USD/t", "#3a7c91"),
    "LME_CU": ("LME copper", "lme_copper_3m_westmetall_2008-2026_import.csv", "USD/t", "#b47537"),
}


def reported(data_dir: Path, market: str) -> pd.DataFrame:
    if market in {"NYMEX_PL", "COMEX_GC", "COMEX_SI"}:
        cot_file = ("cftc_disaggregated_futures_only_gc_si.csv" if market in {"COMEX_GC", "COMEX_SI"}
                    else "cftc_disaggregated_futures_only_hg_pl.csv")
        reports = pd.read_csv(data_dir / cot_file)
        reports = reports.loc[reports["market"] == market].copy()
        reports["position_date"] = pd.to_datetime(reports["report_date"])
        reports["reported_net"] = reports["managed_money_net"]
        reports["reported_net_pct_oi"] = reports["managed_money_net_pct_oi"] * 100
        reports["reported_long"] = reports["managed_money_long"]
        reports["reported_short"] = reports["managed_money_short"]
        reports["publication_note"] = "CFTC Tuesday positions, normally released Friday; release timestamp not supplied"
        reports["published_at_utc"] = ""
        category = "CFTC managed money · futures only"
        unit = "contracts"
    else:
        reports = pd.read_csv(data_dir / f"{market.lower()}_cotr_all_categories.csv")
        reports = reports.loc[(reports["market"] == market) &
                              (reports["category"] == "investment_funds") &
                              (reports["position_bucket"] == "total")].copy()
        reports["position_date"] = pd.to_datetime(reports["position_date"])
        reports["reported_net"] = reports["net_lots"]
        reports["reported_net_pct_oi"] = (reports["long_share_oi"] - reports["short_share_oi"]) * 100
        reports["reported_long"] = reports["long_lots"]
        reports["reported_short"] = reports["short_lots"]
        reports["publication_note"] = "LME Friday positions, normally released Tuesday; actual UTC release timestamp included"
        category = "LME investment funds · total"
        unit = "lots"
    if reports.empty or reports["position_date"].duplicated().any():
        raise ValueError(f"Missing or duplicate {market} positioning reports")
    if not np.allclose(reports["reported_long"] - reports["reported_short"], reports["reported_net"], atol=.02):
        raise ValueError(f"Reported net does not reconcile: {market}")
    return reports[["position_date", "reported_net", "reported_net_pct_oi", "reported_long",
                    "reported_short", "published_at_utc", "publication_note"]].sort_values("position_date").assign(
                        report_category=category, reported_unit=unit)


def build(market: str, data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = load_csv(data_dir / MARKETS[market][1], market)
    daily = compute_positions(prices)
    daily["rsi14"] = rsi(prices["close"])
    daily = daily.rename(columns={"date": "price_date"})
    reports = reported(data_dir, market)
    weekly = pd.merge_asof(reports, daily[["price_date", "exposure", "rsi14", "close"]],
                           left_on="position_date", right_on="price_date",
                           direction="backward", tolerance=pd.Timedelta(days=7))
    weekly["model_score"] = weekly["exposure"] * 100
    # Comparison begins when both series exist, after the model's warm-up.
    weekly = weekly.loc[weekly["position_date"] >= daily.loc[daily["exposure"].notna(), "price_date"].iloc[0]].copy()
    if weekly["model_score"].notna().sum() < 100:
        raise ValueError(f"Too few matched report weeks for {market}")
    return prices, daily, weekly


def chart(market: str, daily: pd.DataFrame, weekly: pd.DataFrame, path: Path,
          years: int | None = None, frequency: str = "Daily") -> None:
    if frequency not in {"Daily", "Weekly"}:
        raise ValueError("Chart frequency must be Daily or Weekly")
    name, _, unit, color = MARKETS[market]
    if years is not None:
        start = daily["price_date"].iloc[-1] - pd.DateOffset(years=years)
        daily = daily.loc[daily["price_date"] >= start]
        weekly = weekly.loc[weekly["position_date"] >= start]
    if frequency == "Weekly":
        daily = weekly_last_session(daily, "price_date")
    fig, (top, mid, bottom) = plt.subplots(3, 1, figsize=(13.7, 10), sharex=True,
                                            gridspec_kw={"height_ratios": [1.55, 1.1, .8], "hspace": .12})
    fig.patch.set_facecolor("#f5f7fa")
    for ax in (top, mid, bottom):
        ax.set_facecolor("white")
        ax.grid(axis="y", color="#e0e6eb", lw=.8)
        ax.spines[["top", "right"]].set_visible(False)
    top.axhline(0, color="#6c7b86", lw=.75)
    line1, = top.plot(daily["price_date"], daily["exposure"] * 100, color=color,
                      lw=1.45, label="CTA-style model · left")
    top.set_ylim(-105, 105)
    top.set_yticks([-100, -50, 0, 50, 100])
    top.set_ylabel("Model score · −100 to +100", color=color)
    report_ax = top.twinx()
    report_ax.spines[["top", "left"]].set_visible(False)
    report_ax.axhline(0, color="#6c7b86", lw=.6)
    line2, = report_ax.plot(weekly["position_date"], weekly["reported_net_pct_oi"],
                            color="#364c5c", marker="o" if years else None,
                            markersize=2.0, lw=1,
                            label="Reported fund net / OI · right")
    report_ax.set_ylabel("Reported net · % open interest", color="#364c5c")
    top.legend([line1, line2], [line1.get_label(), line2.get_label()], loc="upper left",
               ncol=2, frameon=False, fontsize=9)
    mid.plot(daily["price_date"], daily["close"], color="#344b60", lw=1.25)
    mid.set_ylabel(f"Quote · {unit}")
    bottom.axhspan(30, 70, color="#eff3f6", zorder=0)
    bottom.plot(daily["price_date"], daily["rsi14"], color="#7c6395", lw=1.1)
    bottom.axhline(30, color="#89959e", lw=.8, ls="--")
    bottom.axhline(70, color="#89959e", lw=.8, ls="--")
    bottom.set_ylim(0, 100)
    bottom.set_yticks([0, 30, 50, 70, 100])
    bottom.set_ylabel("RSI(14)")
    bottom.xaxis.set_major_locator(mdates.YearLocator(1 if years else 2))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    bottom.set_xlim(daily["price_date"].iloc[0], daily["price_date"].iloc[-1])
    latest = weekly.iloc[-1]
    fig.suptitle(f"{name} · model vs reported positioning · {frequency.lower()} display", x=.08, y=.992,
                 ha="left", fontsize=18, fontweight="bold")
    fig.text(.08, .947, f"Model {daily['exposure'].iloc[-1]*100:+.1f} on {daily['price_date'].iloc[-1].date()}"
             f"    Reported net {latest['reported_net']:+,.0f} {latest['reported_unit']}"
             f" ({latest['reported_net_pct_oi']:+.1f}% OI) on {latest['position_date'].date()}", fontsize=10)
    fig.text(.08, .027, "Weekly report plotted at its POSITION date; released later (LME usually Tuesday, CFTC usually Friday). "
             "Do not trade on the report before release.\n"
             "LME: investment funds and rolling 3M quote. Precious metals: CFTC futures-only managed money and unverified Yahoo continuous quote. "
             "Model is not observed CTA holdings.", fontsize=8.8, color="#4e5f6e")
    fig.subplots_adjust(left=.085, right=.91, top=.90, bottom=.125)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--markets", nargs="+", choices=MARKETS, default=list(MARKETS))
    parser.add_argument("--full-frequency", choices=["Weekly", "Daily"], default="Weekly",
                        help="Chart display only; daily model and RSI calculations are unchanged")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for market in args.markets:
        prices, daily, weekly = build(market, args.data_dir)
        stem = market.lower()
        weekly.to_csv(args.output_dir / f"{stem}_model_vs_reported_weekly.csv", index=False)
        for suffix, years in (("full", None), ("3y", 3)):
            chart(market, daily, weekly, args.output_dir / f"{stem}_comparison_{suffix}.png", years,
                  args.full_frequency if years is None else "Daily")
        snapshot = make_snapshot(prices, daily.rename(columns={"price_date": "date"}))
        scenarios = scenario_table(snapshot)
        scenarios.to_csv(args.output_dir / f"{stem}_conditional_shocks.csv", index=False)
        triggers = trigger_levels(snapshot)
        pair = weekly.dropna(subset=["model_score", "reported_net_pct_oi"])
        last = weekly.iloc[-1]
        row = {"market": market, "model_date": daily["price_date"].iloc[-1].date(),
               "latest_quote": snapshot.raw_price, "price_unit": MARKETS[market][2],
               "model_score": round(daily["exposure"].iloc[-1] * 100, 2),
               "rsi14": round(daily["rsi14"].iloc[-1], 2),
               "report_position_date": last["position_date"].date(),
               "reported_net": last["reported_net"], "reported_unit": last["reported_unit"],
               "reported_net_pct_oi": round(last["reported_net_pct_oi"], 2),
               "matched_weeks": len(pair), "pearson_same_position_date": round(pair["model_score"].corr(pair["reported_net_pct_oi"]), 3),
               "sign_agreement_pct": round((np.sign(pair["model_score"]) == np.sign(pair["reported_net_pct_oi"])).mean() * 100, 1),
               **triggers}
        summaries.append(row)
        print(row, flush=True)
    pd.DataFrame(summaries).to_csv(args.output_dir / "comparison_summary.csv", index=False)


if __name__ == "__main__":
    main()
