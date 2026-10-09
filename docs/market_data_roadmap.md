# Next-market data and positioning plan

## Scope

COMEX copper (`COMEX_HG`), NYMEX platinum (`NYMEX_PL`), and SGX IODEX 62% Fe
iron ore (`SGX_IO62`) have market definitions. They have **no bundled daily
futures price series** and cannot produce current model scores yet. The dashboard
supports a validated manual upload using `date,market,contract,close,signal_close,source`.
The `contract_size` metadata is in `contract_unit`; SGX size remains unset until
the exact contract is verified against current specifications. Never enter a
spot index as if it were a monthly futures settlement.

## Free public positioning benchmark

Run from the repository root:

```bash
python -m cta_models.cot --output dashboard/data/cftc_disaggregated_futures_only_hg_pl.csv
```

The script calls CFTC's public Socrata dataset `72hh-3qpy`, paginates and
validates the full disaggregated futures-only series for codes `085692` (COMEX
copper) and `076651` (NYMEX platinum). CSV includes the Tuesday report date,
managed-money long, short, spreading, net, open interest, and net/OI. It does
not include options, actual CTA-only positions, or a verified release timestamp.
The CFTC currently allows token-free public API use subject to reasonable use.
Preserve the report date and attach an *observed* publication timestamp before
using any report as an input to a backtest. For historical validation, explicitly
choose futures-only or futures-and-options combined and retain that choice.

LME publishes weekly individual metal COT reports with an Investment Funds
category, normally Friday positions made public Tuesday. Copper, aluminium,
zinc, and nickel have public report pages with individual XLS/XLSX files. The
2026 copper workbook exposes separate fund long/short in columns F/G; row 12
is the total, row 11 the non-risk-reducing positions. A robust import should:

1. Discover reports via the four metal landing pages and maintain a manifest of
   source URL, position date, publication date, file hash, and retrieval date.
2. Parse by workbook **labels** (not hardcoded row/column positions); validate
   metal, date, unit, category and long/short totals. Handle both XLS and XLSX.
3. Retain risk-reducing, other, and total fund positions separately, with the
   percentage-of-open-interest fields; detect duplicates and revised reports.
4. Check permission and redistribution terms before storing bulk LME report
   contents in GitHub. Current public page yields roughly 2021 onward for
   copper and aluminium; older history may require a separate archive or LME.
5. Join weekly benchmark to *previously generated* daily model scores on
   position date for descriptive calibration; preserve publication timestamps
   for any predictive use. LME's Investment Funds group is not a CTA-only group.

SGX iron ore has no CFTC equivalent. Its public exchange research and weekly
participant-segment publications merit a separate review; do not equate their
fund categories to CFTC managed money without checking definitions.

## Futures prices and realistic returns

For every monthly future obtain daily contract identifier, settlement,
available timestamp, volume, open interest, and preferably session high/low.
Also obtain contract calendar/last trade dates, tick and currency conventions,
and both outgoing/incoming contracts at rolls. Create a named roll rule, save
the *raw contract panel*, a continuous signal series with documented adjustment,
and a separate return series based on held-contract settlement-to-settlement
changes. Avoid a synthetic price jump from switching contracts. Model score
can use one settlement per day; OHLC is needed for high/low rules and execution
assumptions, not for close-only RSI.

CME product pages display recent settlements, but CME markets full historical
datasets through DataMine. SGX lists historical commodities daily settlement
prices; confirm contract-by-contract depth, format, rights, and automated access
before treating it as a clean feed. SGX's 62% Fe expiring-contract reference
changes at January 2026; treat that historical index transition explicitly.
For all three markets, compare accessible public coverage and licensing with
the eventual Bloomberg contract-month pull.

## Research gates

- Build free CFTC history first and compare it to model output descriptively.
- Add each market's independently verified price panel and roll calendar.
- Test one-day-lagged exposure, cost, roll, and contract-dollar P&L against
  buy-and-hold and single-horizon trend baselines, with a held-out period.
- Keep RSI-14 as a separate close-only experiment until its out-of-sample
  contribution to positioning calibration and/or returns is established.

Sources: https://publicreporting.cftc.gov/stories/s/Disaggregated-Futures-Only/ubmb-6exi/ ;
https://www.lme.com/market-data/reports-and-data/commitments-of-traders ;
https://www.sgx.com/research-education/derivatives ;
https://rulebook.sgx.com/rulebook/appendix-1-final-settlement-price ;
https://www.cmegroup.com/market-data/real-time-and-historical-data.html .
