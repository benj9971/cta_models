# Optional copper CTA dashboard

This additive package imports the existing modelling engine. No existing model,
CLI, report, dependency file or configuration is changed. Install Streamlit only
when using the dashboard. No live data fetch, scheduler or public deployment is
included. The engine remains usable without dashboard dependencies.

## Start from the repository root

```bash
python -m pip install -e . -r dashboard/requirements.txt
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Open http://localhost:8501 on your laptop. For an iPhone, open this repository in
your GitHub Codespace and run:

```bash
python -m pip install -e . -r dashboard/requirements.txt
python -m streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false
```

In Codespaces, open the **Ports** panel, forward port **8501**, keep its visibility
**Private**, and open the forwarded URL in Safari while signed into GitHub.
Codespaces' authenticated port forwarding supplies access control. This app does
not implement its own login; do not expose it through an unauthenticated public
host. A private repository alone does not make a running web server private.
Keep Streamlit's default XSRF and CORS protections enabled. Stop the process with
Ctrl+C and stop the Codespace when finished. No hosting service is provisioned.

## Manual workflow

1. Choose LME_CU or COMEX_HG and synthetic demo or CSV upload.
2. Press **Load / refresh**. Until pressed, changes to load controls do not change
   displayed results. The loaded market/date stays in the header.
3. Use the vertical view selector: Positioning, Price scenarios, Backtests,
   Diagnostics. Charts fit the screen; wide tables scroll horizontally.
4. Download inputs, signals, scenarios or backtest rows as CSV. Ask for changes
   with the loaded market, quote date and the downloaded evidence.

Uploads and results stay in browser-session server memory. There is no global
cache, disk write or upload commit. Restarting the server loses the session.
Invalid uploads preserve the previous successful load with a visible error.
Demo mode and files with SYNTHETIC in any source row carry a persistent banner.
No timestamp or demo number is presented as a live market reading.

## Input contract

Use the existing engine schema:
`date,market,contract,open,high,low,close,signal_close,source`.
Supply one market per file and more than 252 observations for a complete
position; at least 255 are needed for two backtest observations. Existing input
validation remains authoritative. Quote units are USD/t for LME and US cents/lb
for COMEX. `signal_close` must be a documented roll-adjusted series in the same
units as the raw quote. The app does not stitch futures contracts.

Optional columns:

- `available_at`: UTC availability timestamp, checked by the existing importer.
  Shown in diagnostics; not sufficient to prove executable closing-price timing.
- `pnl_return`: finite decimal return on **one unit of notional exposure**, with
  the return interval ending on that row's date. For example, 0.01 means +1%.
  Supply the same value for warm-up rows, or another finite value; all rows are
  validated, though warm-up rows do not enter performance. The user constructs
  the execution/roll-consistent series externally. It is not contract-dollar P&L.

The architecture reads market definitions from the engine, so later metals can
reuse the views when their inputs and demo/provider support are added.

## Backtest definition and limits

Without `pnl_return`, performance uses percentage changes in `signal_close`,
explicitly labelled **adjusted signal-price proxy**. Additive back adjustment can
distort percentage returns; this is research diagnostics, not validated futures
profitability. Raw changing-contract close returns are never used for backtests.

Return ending at date t uses exposure from t-1. This assumes that prior signal
was available and executable before that return interval began. The UI requires
acknowledgement of these assumptions; availability timestamps do not enforce an
exchange closing calendar. Neither a proxy series nor a supplied return series
proves this execution timing. All performance remains labelled research.

Costs = absolute change in held exposure × user cost bps / 10,000, including
entry from flat at the selected window start. The chosen window has no forced
terminal liquidation. Both initial capital and first-day losses enter drawdown.
Equity compounds normalized returns; no leverage beyond the engine's unit cap.
Annualization uses 252 observations/year and Sharpe assumes a zero cash rate.
The benchmark is unit exposure to the same return series with no costs, so its
risk and costs differ. Funding, cash yield, margin, market impact, position size,
contract/tonnage calibration, vendor CTA comparisons and out-of-sample model
selection are not implemented. Short-window annualization is unstable.

## Scenarios and diagnostics

Scenario views reuse the engine's frozen-history/frozen-volatility snapshot and
approximate trigger grid within ±25% of the loaded raw quote. The custom quote
calculator is also conditional, not a multi-day path forecast. A nonpositive
implied adjusted price produces a visible error instead of invented results.

Diagnostics show source labels, raw/adjusted quotes, warm-up, freshness, date
gaps and quote-label changes. Calendar gaps are not verified exchange holidays;
LME rolling prompts may change label every day. No synthetic freshness claim
is made, and source labels are user declarations rather than vendor verification.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests cover existing core behavior, lagged returns, costs, initial drawdown,
input failures and Streamlit load/view/scenario/backtest flows. Streamlit UI
tests skip when its optional dependency is absent.

Implementation references: [Streamlit app testing](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
and [GitHub Codespaces port security](https://docs.github.com/en/codespaces/reference/security-in-github-codespaces).
