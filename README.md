# Copper CTA positioning proxy

An open, auditable **model estimate** of what a group of trend-following rules
would hold in LME and COMEX copper. It is intended as context for discretionary
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

`LME_CU` is USD/t on the rolling three-month prompt; `COMEX_HG` is US cents/lb
on a monthly contract. Market specifications live in `config.py` so further
metals and exchanges can be added without changing the signal code. The
synthetic COMEX contract names and LME prompt dates are illustrative labels,
not exchange calendars or executable roll schedules.

Before analysing real data we will choose the exact closing-price convention,
roll methodology, holiday calendar, Bloomberg fields and as-of timing for each
exchange. The importer checks the optional availability timestamp but cannot
independently prove its accuracy. Bloomberg integration, trade P&L, CFTC
calibration, LME positioning benchmarks, contract/tonnage estimates and a web
dashboard are future stages; none are represented by the demo.

## Repository layout

`src/cta_models/config.py` defines markets and model settings; `data.py`
validates inputs; `synthetic.py` creates controlled scenarios; `model.py`
computes exposure; `scenarios.py` finds conditional changes; `report.py`
exports research output; `cli.py` runs the workflow. `tests/` checks the
primary accounting and timing risks.
