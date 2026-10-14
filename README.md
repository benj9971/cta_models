# Metals CTA positioning proxy

An open, auditable **model estimate** of what a group of trend-following rules
would hold across copper, precious metals and other covered markets. It is intended as context for discretionary
trading. It does **not** observe CTA holdings or forecast actual CTA order flow.

The `demo` command uses **invented prices**. No date or number in its demo
report should be interpreted as a historical or current market observation.
The dashboard also accepts labelled historical and provisional proxy inputs;
read `docs/public_data_and_proxies.md` before interpreting those signals.

## Quick start

Requires Python 3.10 or later.

```bash
python -m pip install -e .
cta-models demo --out-dir output/demo
```

Open `output/demo/report.html`. The run also writes `summary.csv`,
`scenarios.csv`, daily model positions, and synthetic input CSVs. Generated
outputs stay under `output/`, which is ignored by Git.

Run focused checks with `python -m unittest discover -s tests -v`.

For the bundled dashboard and positioning charts on a laptop, install the
optional dependencies and launch from the repository root:

```bash
python -m pip install -e ".[dashboard,data]"
python -m streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit. **Positioning** shows the loaded
market's model, quote and RSI; **Reported comparison** has the eight-market
dual-axis model versus exchange positioning charts, price, RSI, and conditional
price levels. Its charts use bundled inputs independently of the market selected
in the load form. **Price scenarios** evaluates the loaded market, **Diagnostics**
shows its input checks, and **Backtests** provides research-only tests where
permitted by the loaded data. There is no automatic price or positioning update
on dashboard startup; refresh the source scripts and reload the CSVs to update.
The Positioning view defaults to weekly chart display, and the Reported comparison
view offers Daily/Weekly on full history (weekly by default). Weekly retains the
last observed session of each week for model score, quote and RSI; it does not
change the daily model or downloadable history. Three-year comparisons remain daily.

## Model definition

For each market the four horizons are 20, 60, 120 and 252 trading days, with
weights of 10%, 15%, 35% and 40%. A horizon averages:

- a signed, volatility-normalized trailing log return, compressed to [−1, 1]
  by `tanh(z/2)`; and
- the current adjusted price's location relative to the *previous* horizon's
  high and low, clipped to [−1, 1].

The weighted sum is multiplied by `min(1, 15% / realized annual volatility)`.
Realized volatility uses 60 daily log returns with a 5% annual floor. Exposure
is in [−1, 1], expressed in the report as −100% to +100% of **the model's own
risk-limited maximum**. The first 252 sessions have no complete signal.

The signed exposure percentile is its expanding historical rank. It is *not*
the fraction of CTAs that are long. Short horizons are reported individually,
but the 120- and 252-day rules have 75% of the combined weight.

Scenarios replace the latest raw market quote and apply the same absolute price
change to its adjusted signal price. Earlier history and today's volatility
estimate are held fixed. Thus a 10-percentage-point selling trigger is a
conditional **model exposure** change, not a prediction of contracts sold.
The grid searches only within ±25% of the current price.

## Using real daily data later

```bash
cta-models analyze --market LME_CU --input your_daily_copper.csv --out-dir output/lme
```

CSV columns: `date,market,contract,open,high,low,close,signal_close,source`.
An optional `available_at` column is a UTC timestamp when the price was first
available. The input must contain one market and unique dates. The `close`
and OHLC columns are **raw quotes for the active contract**; `signal_close`
is a **documented, roll-adjusted, continuous signal series in the same price
unit**. There is intentionally no implicit stitch based on contract labels:
that would turn a futures roll gap into a false trading signal. The initial
version requires the adjusted series from a vetted data preparation step.

`LME_CU` is USD/t on the rolling three-month prompt; `COMEX_HG` is US cents/lb;
`COMEX_GC` and `COMEX_SI` are USD/troy oz on monthly futures. Market specifications live in `config.py` so further
metals and exchanges can be added without changing the signal code. The
synthetic COMEX contract names and LME prompt dates are illustrative labels,
not exchange calendars or executable roll schedules.

The provisional dashboard is launched with `python -m streamlit run dashboard/app.py`
after installing Streamlit. The chart scripts also require Matplotlib, and
refreshing LME reports requires requests, openpyxl and xlrd. Public LME
investment-fund history and CFTC
managed-money history can be used as distinct positioning benchmarks. Run
`python scripts/chart_lme_investment_funds.py --output-dir output/lme_funds`
for LME positioning/price charts, adding `--refresh` to update the LME archive.
The included Yahoo continuous futures quotes are signal-only proxies and their
backtests are disabled. The LME three-month price imports are published quotes,
not an executable contract-level return series.

Compare platinum, gold, silver, nickel, zinc, aluminium, LME copper and COMEX copper model scores against the
reported fund categories, with price and RSI panels, using
`python scripts/compare_reported_positions.py --output-dir output/position_comparison`.
See `docs/model_vs_reported.md` for position-date alignment, publication lags,
scenario levels and the limits of interpreting a model threshold as a stop.

Latest refresh and validation review: see `docs/cta_review_2026-10-14.md`.
To refresh recent LME reports and the current 2026 quote pages without
re-downloading the complete report archive, run
`python scripts/refresh_lme_recent.py --as-of 2026-10-13`.
Coverage and rolling-window descriptive diagnostics can be reproduced with
`python scripts/audit_coverage.py --output-dir output/audit`.

Before interpreting futures P&L or estimated CTA contracts we still need
verified contract settlements, roll and expiration rules, available-at
timestamps, cost and slippage assumptions, contract sizing and market-specific
calibration. Bloomberg integration and deployment within work infrastructure
remain future stages. The importer checks optional availability timestamps but
cannot independently establish when a vendor first made a quote available.

## Repository layout

`src/cta_models/config.py` defines markets and model settings; `data.py`
validates inputs; `synthetic.py` creates controlled scenarios; `model.py`
computes exposure; `scenarios.py` finds conditional changes; `report.py`
exports research output; `cli.py` runs the workflow. `tests/` checks the
primary accounting and timing risks.
