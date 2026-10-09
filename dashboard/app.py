"""Launch from the repo root: python -m streamlit run dashboard/app.py."""

from pathlib import Path
import sys

# Streamlit executes this as a file. Make the additive package importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from cta_models.config import MARKETS
from cta_models.scenarios import scenario_table, trigger_levels
from dashboard.analytics import backtest, build_run, component_table, diagnostics

HISTORICAL_FILES = {
    "LME_CU": ("LME copper history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_copper_3m_westmetall_2008-2026_import.csv"),
    "LME_NI": ("LME nickel history (2008–2026)", Path(__file__).resolve().parent / "data" / "lme_nickel_3m_westmetall_2008-2026_import.csv"),
}
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
            if source == "Synthetic demo" and market == "LME_NI":
                raise ValueError("The synthetic demo is for copper only; choose nickel history or upload a nickel CSV")
            payload = (HISTORICAL_LABELS[source][1].read_bytes() if source in HISTORICAL_LABELS else
                       None if source == "Synthetic demo" else upload.getvalue())
            new_run = build_run(market, payload)
            st.session_state["run"] = new_run
            st.session_state["run_origin"] = ("historical" if source in HISTORICAL_LABELS else
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
if run.synthetic:
    st.warning("SYNTHETIC DEMO — invented prices and performance. No historical or current market inference.")
elif st.session_state.get("run_origin") == "historical":
    st.info("WESTMETALL LME 3-MONTH HISTORY — one published daily quote, USD/t. The CSV's close field is an import alias, not a closing bar. No live feed or executable P&L is implied.")
    if snapshot.market == "LME_NI":
        st.warning("NICKEL DATA NOTE — March 2022 has no published three-month quote from 8–25 March in this source. The March 7 squeeze and March 28 resumption are separated by a 21-day gap. Model signals span observed sessions; proxy backtest returns across this interval are not executable.")
else:
    st.info("UPLOADED DATA — source and roll methodology are user supplied. No live feed is connected.")
if not run.synthetic:
    age = (pd.Timestamp.now(tz="UTC").date() - snapshot.as_of.date()).days
    if age > 4 or age < 0:
        st.warning(f"Last observation is {snapshot.as_of.date()} (calendar age: {age} days). Check freshness and dates.")
st.caption(f"Loaded: {snapshot.market} · quote date {snapshot.as_of.date()} · refreshed {run.loaded_at:%Y-%m-%d %H:%M UTC}")
st.caption("−100 to +100 measures exposure against the model's risk limit; it is not observed CTA holdings or contracts.")
page = st.radio("View", ["Positioning", "Price scenarios", "Backtests", "Diagnostics"], label_visibility="collapsed")

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
    chart = run.positions.set_index("date")
    st.subheader("Position history (points)")
    st.line_chart(chart[["exposure", "raw_ensemble"]].mul(100).rename(columns={"exposure": "Risk-scaled position", "raw_ensemble": "Unscaled ensemble"}))
    st.subheader(f"Raw quote history ({unit})")
    st.line_chart(chart[["close"]])
    with st.expander("Individual signal history"):
        st.line_chart(chart[[f"signal_{h}" for h in snapshot.config.horizons]].mul(100))
    st.download_button("Download position history", run.positions.to_csv(index=False).encode(),
                       f"{snapshot.market.lower()}_positions.csv", "text/csv", width="stretch", on_click="ignore")

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
    st.caption("The model uses 75% weight on 120/252-session rules. Scenario calculations preserve today's risk scale. Contract and tonnage calibration and positioning benchmark comparisons are not yet available.")
    st.download_button("Download loaded inputs", run.prices.to_csv(index=False).encode(),
                       f"{snapshot.market.lower()}_inputs.csv", "text/csv", on_click="ignore")
