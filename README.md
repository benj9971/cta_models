# Metals CTA positioning proxy

An open, auditable **model estimate** of what a group of trend-following rules
would hold in LME copper, LME nickel and COMEX copper. It is intended as context for discretionary
trading. It does **not** observe CTA holdings or forecast actual CTA order flow.

The initial runnable demo uses **invented prices**. No date or number in its
report should be interpreted as a historical or current market observation.

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

## Using real daily data

```bash
cta-models analyze --market LME_CU --input your_daily_copper.csv --out-dir output/lme
```

Required CSV columns: `date,market,contract,close,signal_close,source`.
If true OHLC is available, supply **all three** additional `open,high,low`
columns. Never fill missing OHLC with a single daily quote.
An optional `available_at` column is a UTC timestamp when the price was first
available. The input must contain one market and unique dates. The `close`
and any OHLC columns are **raw quotes for the active contract**; `signal_close`
is a **documented continuous signal series in the same price unit**. For
monthly futures this normally requires a documented roll adjustment. An LME
rolling three-month published quote can be used directly for research, with
`contract=3M_ROLLING` and `signal_close=close`; the schema's `close` name is
only an import alias and does not turn that quote into an exchange close.
There is intentionally no implicit stitch based on contract labels:
that would turn a futures roll gap into a false trading signal. The initial
version requires the continuous series from a vetted data preparation step.

The public Westmetall LME three-month series starts in 2008 and contains one
published quote per source date, not open/high/low/close bars. It is suitable
for a signal stress test, but its percentage changes are not executable
futures P&L. Record the source and quote convention when importing it.

The included nickel file is `dashboard/data/lme_nickel_3m_westmetall_2008-2026_import.csv`.
Analyse it with:

```bash
cta-models analyze --market LME_NI --input dashboard/data/lme_nickel_3m_westmetall_2008-2026_import.csv --out-dir output/lme_nickel
```

It contains 4,615 dated USD/t quotes from 17 June 2008 through 8 October 2026,
from the [Westmetall nickel yearly tables](https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Ni_cash&year=2026).
Earlier 2008 quotes through 19 February are excluded from the import series
because the source has no nickel three-month values until 17 June, a roughly
four-month gap that would distort observation-based horizons. One duplicate
Saturday quote was also excluded. The source has no three-month values on
8–25 March 2022, between the 7 March squeeze quote and 28 March resumption.
The model counts published observations; its signal can be inspected across
this interruption, but a proxy return over the 21-day gap is not an executable
trade and the 2022 episode needs separate robustness checks. Do not interpret
the full-period backtest as a realistic trading result.

`LME_CU` and `LME_NI` are USD/t on the rolling three-month prompt; `COMEX_HG` is US cents/lb
on a monthly contract. Market specifications live in `config.py` so further
metals and exchanges can be added without changing the signal code. The
synthetic COMEX contract names and LME prompt dates are illustrative labels,
not exchange calendars or executable roll schedules.

Before analysing real data we will choose the exact closing-price convention,
roll methodology, holiday calendar, Bloomberg fields and as-of timing for each
exchange. The importer checks the optional availability timestamp but cannot
independently prove its accuracy. Bloomberg integration, trade P&L, CFTC
calibration, LME positioning benchmarks and contract/tonnage estimates are
future stages; none are represented by the demo. The optional dashboard is
described in `dashboard/README.md`.

## Repository layout

`src/cta_models/config.py` defines markets and model settings; `data.py`
validates inputs; `synthetic.py` creates controlled scenarios; `model.py`
computes exposure; `scenarios.py` finds conditional changes; `report.py`
exports research output; `cli.py` runs the workflow. `tests/` checks the
primary accounting and timing risks.

