"""Chart weekly LME investment-fund positioning against observed 3M quotes.

Run from the repository root:
python scripts/chart_lme_investment_funds.py --output-dir output/lme_funds

Investment funds is the LME's published category, not CFTC managed money and
not observed CTA holdings. The report position date precedes publication.
"""

import argparse
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


HERE = Path(__file__).resolve().parents[1]
DATA = HERE / "dashboard" / "data"
MARKETS = {
    "LME_CU": ("Copper", "lme_copper_3m_westmetall_2008-2026_import.csv", "#b87333"),
    "LME_AL": ("Aluminium", "lme_aluminium_3m_westmetall_2008-2026_staged.csv", "#507a96"),
    "LME_ZN": ("Zinc", "lme_zinc_3m_westmetall_2008-2026_staged.csv", "#687c55"),
    "LME_NI": ("Nickel", "lme_nickel_3m_westmetall_2008-2026_import.csv", "#756ba1"),
}


def series(market: str, data_dir: Path = DATA) -> pd.DataFrame:
    if market not in MARKETS:
        raise ValueError(f"Unknown market {market}")
    cot = pd.read_csv(data_dir / f"{market.lower()}_cotr_all_categories.csv")
    cot = cot.loc[(cot["market"] == market) &
                  (cot["category"] == "investment_funds") &
                  (cot["position_bucket"] == "total")].copy()
    cot["position_date"] = pd.to_datetime(cot["position_date"])
    cot["published_at_utc"] = pd.to_datetime(cot["published_at_utc"], utc=True)
    if cot.empty or cot["position_date"].duplicated().any():
        raise ValueError(f"No unique LME investment-fund series for {market}")
    if (cot["published_at_utc"].dt.tz_localize(None) < cot["position_date"]).any():
        raise ValueError("Publication cannot precede the position date")
    if not ((cot["long_lots"] - cot["short_lots"] - cot["net_lots"]).abs() < .02).all():
        raise ValueError("Net lots do not reconcile")
    prices = pd.read_csv(data_dir / MARKETS[market][1], usecols=["date", "market", "close", "source"])
    if not (prices["market"] == market).all():
        raise ValueError("Price market label does not match")
    prices["price_date"] = pd.to_datetime(prices.pop("date"))
    if prices["price_date"].duplicated().any():
        raise ValueError("Duplicate price dates")
    # Use an observed quote from the position day or an earlier trading day.
    # Holiday gaps exceeding seven calendar days remain explicitly unmatched.
    merged = pd.merge_asof(cot.sort_values("position_date"),
                           prices.drop(columns="market").sort_values("price_date"),
                           left_on="position_date", right_on="price_date",
                           direction="backward", tolerance=pd.Timedelta(days=7))
    merged["net_share_oi_pct"] = (merged["long_share_oi"] - merged["short_share_oi"]) * 100
    return merged[["market", "position_date", "published_at_utc", "long_lots", "short_lots",
                   "net_lots", "long_share_oi", "short_share_oi", "net_share_oi_pct",
                   "number_of_traders", "price_date", "close", "source", "source_url"]]


def chart(data: pd.DataFrame, market: str, path: Path, years: int | None = None) -> None:
    metal, _, color = MARKETS[market]
    if years is not None:
        data = data.loc[data["position_date"] >= data["position_date"].max() - pd.DateOffset(years=years)]
    fig, (pos_ax, price_ax) = plt.subplots(2, 1, figsize=(13, 7.6), sharex=True,
                                           gridspec_kw={"height_ratios": [1.3, 1], "hspace": .12})
    fig.patch.set_facecolor("#f5f7fa")
    for ax in (pos_ax, price_ax):
        ax.set_facecolor("white")
        ax.grid(axis="y", color="#e1e6ed", linewidth=.8)
        ax.spines[["top", "right"]].set_visible(False)
    pos_ax.axhline(0, color="#607080", lw=.8)
    pos_ax.plot(data["position_date"], data["net_lots"], color=color, lw=1.7,
                label="Net = long − short")
    pos_ax.fill_between(data["position_date"], data["net_lots"], 0, color=color, alpha=.18)
    pos_ax.plot(data["position_date"], data["long_lots"], color="#2b6d73", lw=.75,
                alpha=.65, label="Long")
    pos_ax.plot(data["position_date"], -data["short_lots"], color="#9b6b7a", lw=.75,
                alpha=.65, label="Short, shown negative")
    pos_ax.set_ylabel("LME investment funds · lots")
    pos_ax.legend(loc="upper left", ncol=3, fontsize=9, frameon=False)
    price_ax.plot(data["price_date"], data["close"], color="#43586c", lw=1.35)
    price_ax.set_ylabel("LME 3M quote · USD/t")
    price_ax.xaxis.set_major_locator(mdates.YearLocator(1 if years else 2))
    price_ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    last = data.iloc[-1]
    fig.suptitle(f"LME {metal} · investment-fund positions and 3M price",
                 x=.075, y=.988, ha="left", fontweight="bold", fontsize=18)
    fig.text(.075, .932, f"Position dates {data['position_date'].iloc[0].date()}–{last['position_date'].date()}"
             f"    Latest net {last['net_lots']:+,.0f} lots    Price {last['close']:,.2f} USD/t",
             fontsize=10)
    fig.text(.075, .035, "Weekly positions use the report's position date (usually Friday), but become known only on publication (usually Tuesday).\n"
             "Price is the most recent observed Westmetall LME 3M quote on/before that date. "
             "Investment funds are not CTA holdings or CFTC managed money.", fontsize=9, color="#4d5f6d")
    fig.subplots_adjust(left=.09, right=.98, top=.88, bottom=.14)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--market", choices=[*MARKETS, "all"], default="all")
    parser.add_argument("--refresh", action="store_true",
                        help="Pull all linked public LME COT workbooks before charting")
    args = parser.parse_args()
    if args.refresh:
        subprocess.run([sys.executable, str(HERE / "scripts" / "fetch_lme_cotr.py"),
                        "--output-dir", str(args.data_dir)], check=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for market in MARKETS if args.market == "all" else [args.market]:
        data = series(market, args.data_dir)
        stem = market.lower() + "_investment_funds"
        data.to_csv(args.output_dir / f"{stem}_weekly.csv", index=False)
        chart(data, market, args.output_dir / f"{stem}_full.png")
        chart(data, market, args.output_dir / f"{stem}_3y.png", years=3)
        last = data.iloc[-1]
        print(f"{market}: {len(data)} reports {data['position_date'].min().date()}–"
              f"{last['position_date'].date()}, net {last['net_lots']:+,.0f} lots, "
              f"{data['close'].notna().sum()} matched quotes, last price date {last['price_date'].date()}")


if __name__ == "__main__":
    main()
