"""Launch from the repo root: python -m streamlit run dashboard/app.py."""

from pathlib import Path
from io import BytesIO
import sys

# Streamlit executes this as a file. Make the additive package importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from cta_models.config import MARKETS
from cta_models.charting import weekly_last_session
from cta_models.indicators import rsi
from cta_models.scenarios import scenario_table, trigger_levels
from dashboard.analytics import backtest, build_run, component_table, diagnostics

HISTORICAL_FILES = {
    "LME_CU": ("LME copper history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_copper_3m_westmetall_2008-2026_import.csv"),
    "LME_NI": ("LME nickel history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_nickel_3m_westmetall_2008-2026_import.csv"),
    "LME_ZN": ("LME zinc history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_zinc_3m_westmetall_2008-2026_staged.csv"),
    "LME_AL": ("LME aluminium history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_aluminium_3m_westmetall_2008-2026_staged.csv"),
    "COMEX_HG": ("COMEX copper Yahoo continuous proxy (2000–2026)", Path(__file__).resolve().parent / "data" / "comex_hg_yahoo_research_proxy.csv"),
    "NYMEX_PL": ("NYMEX platinum Yahoo continuous proxy (2010–2026)", Path(__file__).resolve().parent / "data" / "nymex_pl_yahoo_research_proxy.csv"),
    "COMEX_GC": ("COMEX gold Yahoo continuous proxy (2000–2026)", Path(__file__).resolve().parent / "data" / "comex_gc_yahoo_research_proxy.csv"),
    "COMEX_SI": ("COMEX silver Yahoo continuous proxy (2000–2026)", Path(__file__).resolve().parent / "data" / "comex_si_yahoo_research_proxy.csv"),
    "SGX_IO62": ("Iron ore CME TIO proxy for SGX (2010–2026)", Path(__file__).resolve().parent / "data" / "sgx_io62_yahoo_research_proxy.csv"),
}
PROXY_MARKETS = {"COMEX_HG", "NYMEX_PL", "COMEX_GC", "COMEX_SI", "SGX_IO62"}
HISTORICAL_LABELS = {label: (market, path) for market, (label, path) in HISTORICAL_FILES.items()}

st.set_page_config(page_title="Metals CTA", page_icon="📈", layout="centered")
st.title("Metals CTA")
st.caption("Positioning research · manual updates")

if "run" not in st.session_state:
    try:
        st.session_state["run"] = build_run("LME_CU", HISTORICAL_FILES["LME_CU"][1].read_bytes())
        st.session_state["run_origin"] = "historical"
    except (OSError, ValueError, KeyError, IndexError, TypeError, UnicodeError) as error:
        st.session_state["load_error"] = f"Included history could not be loaded: {error}"

with st.expander("Load or refresh data", expanded="run" not in st.session_state):
    with st.form("load"):
        market = st.selectbox("Market", list(MARKETS))
        source = st.radio("Input", [*HISTORICAL_LABELS, "Synthetic demo", "Upload CSV"])
        upload = st.file_uploader("Daily prices CSV", type=["csv"])
        submitted = st.form_submit_button("Load / refresh", width="stretch")
    if submitted:
        try:
            if source == "Upload CSV" and upload is None:
                raise ValueError("Choose a CSV before loading")
            if source in HISTORICAL_LABELS and market != HISTORICAL_LABELS[source][0]:
                raise ValueError(f"The selected history is for {HISTORICAL_LABELS[source][0]}; select that market")
            if source == "Synthetic demo" and market not in ("LME_CU", "COMEX_HG"):
                raise ValueError("The synthetic demo is for copper only; choose matching history or upload a CSV")
            payload = (HISTORICAL_LABELS[source][1].read_bytes() if source in HISTORICAL_LABELS else
                       None if source == "Synthetic demo" else upload.getvalue())
            new_run = build_run(market, payload)
            st.session_state["run"] = new_run
            st.session_state["run_origin"] = ("proxy" if source in HISTORICAL_LABELS and market in PROXY_MARKETS else
                                               "historical" if source in HISTORICAL_LABELS else
                                               "synthetic" if source == "Synthetic demo" else "upload")
            st.session_state.pop("load_error", None)
        except (OSError, ValueError, KeyError, IndexError, TypeError, UnicodeError) as error:
            st.session_state["load_error"] = str(error)

if "load_error" in st.session_state:
    st.error(f"Data not updated: {st.session_state['load_error']}. Any displayed results are from the previous successful load.")
if "run" not in st.session_state:
    st.info("Choose a market and press Load / refresh to begin. No live feed is connected.")
    st.stop()

run = st.session_state["run"]
snapshot = run.snapshot
latest = run.positions.iloc[-1]
unit = MARKETS[snapshot.market].price_unit
proxy_source = (st.session_state.get("run_origin") == "proxy" or
                run.prices["source"].astype(str).str.contains("UNVERIFIED_CONTINUOUS_SIGNAL_PROXY", case=False, regex=False).any())
if run.synthetic:
    st.warning("SYNTHETIC DEMO — invented prices and performance. No historical or current market inference.")
elif st.session_state.get("run_origin") == "historical":
    st.info("WESTMETALL LME 3-MONTH HISTORY — one published daily quote, USD/t. The CSV's close field is an import alias, not a closing bar. No live feed or executable P&L is implied.")
    if snapshot.market == "LME_NI":
        st.warning("NICKEL DATA NOTE — this source has no three-month quote from 8–25 March 2022. Its March 7 squeeze quote and next quote on March 28 are separated by a 21-day gap; LME trading resumed on March 16. Model signals span observed quote sessions, and proxy backtest returns across this interval are not executable.")
elif proxy_source:
    st.warning("SIGNAL-ONLY PRICE PROXY — Yahoo continuous futures quotes. Contract months, roll timing and adjustment are unverified. Iron ore uses CME TIO, not an SGX FEF settlement. These are model estimates, not observed CTA holdings or executable P&L.")
else:
    st.info("UPLOADED DATA — source and roll methodology are user supplied. No live feed is connected.")
if not run.synthetic:
    age = (pd.Timestamp.now(tz="UTC").date() - snapshot.as_of.date()).days
    if age > 4 or age < 0:
        st.warning(f"Last observation is {snapshot.as_of.date()} (calendar age: {age} days). Check freshness and dates.")
st.caption(f"Loaded: {snapshot.market} · quote date {snapshot.as_of.date()} · refreshed {run.loaded_at:%Y-%m-%d %H:%M UTC}")
st.caption("−100 to +100 measures exposure against the model's risk limit; it is not observed CTA holdings or contracts.")
page = st.radio("View", ["Positioning", "Reported comparison", "Price scenarios", "Backtests", "Diagnostics"], label_visibility="collapsed")

if page == "Positioning":
    valid = run.positions.dropna(subset=["exposure"])
    weekly = (latest["exposure"] - valid["exposure"].iloc[-6]) * 100 if len(valid) >= 6 else None
    st.metric("Overall model position", f"{latest['exposure'] * 100:+.1f}",
              None if weekly is None else f"{weekly:+.1f} points / 5 sessions")
    st.metric(f"Latest quote ({unit})", f"{snapshot.raw_price:,.2f}")
    st.metric("Risk scale", f"{latest['risk_scale'] * 100:.1f}%")
    st.caption(f"Realized annual volatility: {latest['volatility']:.1%} · signed historical percentile: "
               + ("not enough history" if pd.isna(latest['exposure_percentile']) else f"{latest['exposure_percentile']:.0f}th"))
    st.subheader("Signals by horizon")
    st.dataframe(component_table(run).round(2), hide_index=True, width="stretch")
    frequency = st.radio("Chart frequency", ["Weekly", "Daily"], horizontal=True)
    st.caption("Weekly shows the last observed session in each week, including the latest. RSI and model signals are still calculated daily; downloads retain every session.")
    chart = run.positions if frequency == "Daily" else weekly_last_session(run.positions)
    chart = chart.set_index("date")
    st.subheader("Position history (points)")
    st.line_chart(chart[["exposure", "raw_ensemble"]].mul(100).rename(columns={"exposure": "Risk-scaled position", "raw_ensemble": "Unscaled ensemble"}))
    st.subheader(f"Raw quote history ({unit})")
    st.line_chart(chart[["close"]])
    st.subheader("RSI(14) · daily calculation")
    daily_rsi = pd.DataFrame({"date": run.prices["date"], "RSI(14)": rsi(run.prices["close"]).to_numpy()})
    if frequency == "Weekly":
        daily_rsi = weekly_last_session(daily_rsi)
    st.line_chart(pd.DataFrame({"RSI(14)": daily_rsi["RSI(14)"].to_numpy(),
                                "30": 30, "70": 70}, index=chart.index))
    with st.expander("Individual signal history"):
        st.line_chart(chart[[f"signal_{h}" for h in snapshot.config.horizons]].mul(100))
    st.download_button("Download position history", run.positions.to_csv(index=False).encode(),
                       f"{snapshot.market.lower()}_positions.csv", "text/csv", width="stretch", on_click="ignore")

elif page == "Reported comparison":
    st.subheader("Model vs published fund positions")
    st.caption("Bundled research histories. Weekly reported positions are drawn at their position dates, but became public later. LME investment funds are not the same classification as CFTC managed money or observed CTA holdings.")
    try:
        from scripts.compare_reported_positions import build as build_comparison, chart as comparison_chart, MARKETS as COMPARISON_MARKETS, DATA as COMPARISON_DATA
        comparison_market = st.selectbox("Comparison market", list(COMPARISON_MARKETS),
                                         index=list(COMPARISON_MARKETS).index(snapshot.market) if snapshot.market in COMPARISON_MARKETS else 0)
        window = st.radio("Window", ["Last 3 years", "Full history"], horizontal=True)
        frequency = (st.radio("Chart frequency", ["Weekly", "Daily"], horizontal=True)
                     if window == "Full history" else "Daily")
        st.caption(f"{frequency} chart display. Model signals and RSI are calculated from daily closes; published fund positions remain weekly.")
        comp_prices, comp_daily, comp_weekly = build_comparison(comparison_market, COMPARISON_DATA)
        figure = BytesIO()
        comparison_chart(comparison_market, comp_daily, comp_weekly, figure,
                         3 if window == "Last 3 years" else None, frequency)
        st.image(figure.getvalue(), width="stretch")
        matched = comp_weekly.dropna(subset=["model_score", "reported_net_pct_oi"])
        st.caption(f"{len(matched)} matched report dates · same-date correlation "
                   f"{matched['model_score'].corr(matched['reported_net_pct_oi']):.2f}. "
                   "This is a descriptive comparison, not a predictive test.")
        from cta_models.model import make_snapshot
        comp_snapshot = make_snapshot(comp_prices, comp_daily.rename(columns={"price_date": "date"}))
        st.subheader("Conditional price levels")
        st.caption("One-quote shocks with today's volatility and earlier prices held fixed. Rebalance markers, not trade stops or forecasts.")
        shocks = scenario_table(comp_snapshot)
        st.dataframe(shocks[["price_change_pct", "scenario_price", "exposure_pct", "change_pp"]].round(2),
                     hide_index=True, width="stretch")
        levels = trigger_levels(comp_snapshot)
        st.dataframe(pd.DataFrame([{"Model threshold": label, "Quote": value} for label, value in levels.items()]).round(2),
                     hide_index=True, width="stretch")
        st.download_button("Download weekly comparison", comp_weekly.to_csv(index=False).encode(),
                           f"{comparison_market.lower()}_model_vs_reported.csv", "text/csv", on_click="ignore")
    except (ImportError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        st.error(f"Could not produce comparison chart: {error}. Install Matplotlib and check the bundled data.")

elif page == "Price scenarios":
    st.subheader("Conditional price scenarios")
    st.caption("Replaces the latest quote while holding previous history and volatility fixed. These are exposure changes, not forecast orders. Trigger levels are approximate grid crossings within ±25%.")
    try:
        table = scenario_table(snapshot)
        st.line_chart(table.set_index("price_change_pct")[["exposure_pct"]].rename(columns={"exposure_pct": "Model position (points)"}))
        st.dataframe(table[["price_change_pct", "scenario_price", "exposure_pct", "change_pp"]].round(2), hide_index=True, width="stretch")
        triggers = trigger_levels(snapshot)
        labels = {"sell_10pp": "Sell 10 points", "buy_10pp": "Buy 10 points",
                  "direction_flip_down": "Flip to short", "direction_flip_up": "Flip to long"}
        st.dataframe(pd.DataFrame([{"Trigger": labels[k], f"Quote ({unit})": "Unavailable in search range" if v is None else f"{v:,.2f}"} for k, v in triggers.items()]), hide_index=True, width="stretch")
        st.download_button("Download scenarios", table.to_csv(index=False).encode(), "scenarios.csv", "text/csv", on_click="ignore")
    except ValueError as error:
        st.warning(f"Some scenario prices are incompatible with the adjusted series: {error}")
    with st.form("custom_scenario"):
        price = st.number_input(f"Your scenario quote ({unit})", min_value=0.01, value=float(snapshot.raw_price), format="%.2f")
        evaluate = st.form_submit_button("Evaluate price", width="stretch")
    if evaluate:
        try:
            exposure, components = snapshot.at_price(price)
            st.metric("Scenario position", f"{exposure * 100:+.1f}", f"{(exposure - latest['exposure']) * 100:+.1f} points vs loaded quote")
            st.dataframe(pd.DataFrame([{"Horizon": h, "Signal (points)": v * 100} for h, v in components.items()]).round(2), hide_index=True)
        except ValueError as error:
            st.error(str(error))

elif page == "Backtests":
    if proxy_source:
        st.warning("Backtests are unavailable for these bundled Yahoo continuous price proxies. Supply a verified, timestamped and roll-aware return series to evaluate futures performance.")
        st.stop()
    st.subheader("Research backtest")
    st.warning("Research performance, not executable futures P&L. Positions are lagged one observation. Adjusted-price percentage returns may be distorted by the roll method. Funding, margin, cash yield and market impact are excluded.")
    st.caption("Execution assumption: the previous observation's signal is available and executable before the measured return interval begins. Availability timestamps are diagnostic only; the test does not enforce an exchange closing calendar. Supplied returns require the same timing alignment.")
    bases = ["Adjusted signal-price proxy"]
    if "pnl_return" in run.prices:
        bases.append("Supplied pnl_return")
    valid = run.positions.loc[run.positions["exposure"].shift(1).notna(), "date"]
    if len(valid) < 2:
        st.info("Need at least two return observations after the model warm-up. Upload a longer history.")
        st.stop()
    with st.form("backtest"):
        basis = st.selectbox("Return series", bases)
        cost = st.number_input("Cost per unit of exposure turnover (bps)", min_value=0.0, max_value=100.0, value=2.0, step=0.5)
        date_range = st.date_input("Evaluation dates", value=(valid.iloc[0].date(), valid.iloc[-1].date()),
                                   min_value=valid.iloc[0].date(), max_value=valid.iloc[-1].date())
        accepted = st.checkbox("I understand the return-series and execution-timing assumptions")
        calculate = st.form_submit_button("Run backtest", width="stretch")
    if calculate:
        try:
            if not accepted:
                raise ValueError("Acknowledge the assumptions before running the research backtest")
            if len(date_range) != 2 or date_range[0] > date_range[1]:
                raise ValueError("Select a valid start and end date")
            result, metrics = backtest(run, cost, "provided" if basis == "Supplied pnl_return" else "signal_proxy", *date_range)
            st.caption(f"{basis} · {cost:g} bps per exposure unit · {len(result)} observations · window starts flat; entry cost charged; no terminal liquidation")
            for key in ("Total return", "Annualized return", "Max drawdown"):
                st.metric(key, f"{metrics[key]:.1%}")
            st.dataframe(pd.DataFrame([{"Metric": k, "Value": v} for k, v in metrics.items()]).round(4), hide_index=True)
            st.caption("Annualization assumes 252 sessions/year. Short samples can give unstable annualized metrics. Sharpe uses a zero cash rate. Benchmark is unscaled unit exposure to the selected return series, with no costs.")
            indexed = result.set_index("date")
            # Plot initial capital explicitly on the preceding observation date.
            prior_date = run.prices.loc[run.prices["date"] < result["date"].iloc[0], "date"].iloc[-1]
            equity = pd.concat([pd.DataFrame({"strategy_equity": [1.0], "benchmark_equity": [1.0]}, index=[prior_date]), indexed[["strategy_equity", "benchmark_equity"]]])
            st.line_chart(equity.rename(columns={"strategy_equity": "Strategy (net)", "benchmark_equity": "Unit exposure benchmark"}))
            st.line_chart(indexed[["drawdown"]].mul(100))
            st.download_button("Download backtest", result.to_csv(index=False).encode(), "backtest.csv", "text/csv", on_click="ignore")
        except (ValueError, TypeError) as error:
            st.error(str(error))

else:
    st.subheader("Data and model diagnostics")
    st.dataframe(diagnostics(run), hide_index=True, width="stretch")
    st.caption("Date gaps are calendar gaps, not proof of missing exchange sessions. LME rolling prompt labels change daily; quote-label changes are not necessarily discrete futures rolls.")
    st.caption("Positive prices, unique dates and required fields passed validation. Complete OHLC bars were checked only if supplied. This cannot verify the vendor's price or adjustment methodology.")
    if "available_at" in run.prices:
        st.caption(f"Latest availability: {run.prices['available_at'].iloc[-1]}")
    st.subheader("Model settings")
    st.json({"horizons": snapshot.config.horizons, "weights": snapshot.config.weights,
             "volatility_lookback": snapshot.config.volatility_lookback,
             "volatility_target": snapshot.config.volatility_target,
             "volatility_floor": snapshot.config.volatility_floor})
    st.caption("The model uses 75% weight on 120/252-session rules. Scenario calculations preserve today's risk scale. The Reported comparison view is descriptive; contract and tonnage calibration remains unavailable.")
    st.download_button("Download loaded inputs", run.prices.to_csv(index=False).encode(),
                       f"{snapshot.market.lower()}_inputs.csv", "text/csv", on_click="ignore")
