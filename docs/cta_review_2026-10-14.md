# CTA repository and dashboard review — 14 October 2026

## Result and scope

Reviewed `benj9971/cta_models` main at `35fb23701435601bb758f8baa919c027f4dd1306`
(9 October 2026), its recent PRs and Actions history, the source/data files,
and the Streamlit app using AppTest. No Actions runs or configured workflow were
present. No running hosted dashboard URL was identified; this verifies the app
code and bundled inputs, not an existing remote deployment.

All nine configured daily price series were refreshed through **13 October 2026**,
the last completed date used for this run. Four LME position archives now reach
**9 October**, with workbook publication on 13 October. Four CFTC managed-money
series now reach **6 October**. These are the latest observations returned by the
source pulls. Tuesday 13 October CFTC positions are not assumed available before
their later release. There is no intraday 14 October observation in these charts.

Three new daily observations were added to each price series, plus a backfilled
7 October platinum observation. Existing overlapping price values were unchanged.
For LME, 24 recent/overlapping workbooks were re-parsed, preserving older archive
rows and the latest publication revision per report. All four quote overlaps had
zero numerical revisions. Each US metal has one new CFTC report week; each LME
metal has one new position week. Yahoo continuous-series mapping and adjustment
remain unverified.

## Latest snapshot

Model scores are on the model's own −100/+100 scale. Reported net/OI is a
different quantity. The two columns also have different observation dates.

| Market | 13 Oct quote | Model | Latest reported net | Net/OI | Position date |
|---|---:|---:|---:|---:|---|
| LME copper | $14,625.50/t | +72.4 | +40,715.10 lots | +9.69% | 9 Oct |
| COMEX copper | 667.80 US cents/lb | +40.6 | +61,134 contracts | +20.11% | 6 Oct |
| LME aluminium | $3,037/t | −48.0 | +124,923.67 lots | +13.95% | 9 Oct |
| LME nickel | $15,630/t | −55.6 | +5,057.69 lots | +1.55% | 9 Oct |
| LME zinc | $3,756/t | +21.8 | +40,071.06 lots | +10.86% | 9 Oct |
| NYMEX platinum | $1,657.40/troy oz | −17.5 | +8,475 contracts | +12.87% | 6 Oct |
| COMEX gold | $4,177.30/troy oz | −25.1 | +110,987 contracts | +28.02% | 6 Oct |
| COMEX silver | $59.161/troy oz | −17.3 | +7,528 contracts | +7.16% | 6 Oct |
| Iron ore: CME TIO proxy for SGX | $90.72/dmt | −67.9 | Missing | Missing | — |

LME investment funds / total and CFTC managed money / futures only are distinct
category benchmarks. Neither measures actual CTA holdings. The current negative
model scores alongside positive reported funds in several metals are real
differences between these series, not a reason to relabel either quantity.

## Coverage and missing inputs

- LME copper quotes: 2 Jan 2008–13 Oct 2026, 4,746 rows. Aluminium, zinc and
  nickel start 17 Jun 2008, with 4,631, 4,632 and 4,618 rows respectively.
- Gold, silver and COMEX copper begin 30 Aug 2000; 6,555, 6,556 and 6,559 rows.
  Platinum begins 4 Jan 2010, 4,218 rows. CME iron ore begins 14 Oct 2010,
  4,010 rows. These are close-only inputs; full OHLC is not present.
- CFTC archives: 1,061 position dates per metal, 13 Jun 2006–6 Oct 2026.
  Platinum comparisons start after the price series' model warm-up: 823 matched
  weeks. Other US markets have 1,061 matched weeks.
- LME archives begin 3 Jan 2020. Copper/aluminium/zinc/nickel have respectively
  350/351/352/353 distinct report dates. Unequal counts and archive gaps are
  retained rather than invented. Nickel has 351 matched weeks and two unmatched
  dates, 18 and 25 March 2022.
- Nickel quote gap: 7–28 March 2022, 21 calendar days. Do not interpret returns
  across it as tradable. The source does not supply 8–25 March 3M quotes.
- Price `available_at` timestamps are absent for all nine inputs. CFTC files
  retain retrieval time but not verified historical publication timestamps;
  LME files retain workbook publication timestamps. A retrieval timestamp does
  not establish when a historical observation became available.
- Silver's approximately −31% vendor move on 30 January 2026 remains a
  contract-level reconciliation item. Platinum's 7 October backfill illustrates
  that a vendor refresh can alter the historical observation set.
- Iron ore remains CME TIO, not SGX FEF; exact SGX settlements, participant
  positioning, benchmark-transition handling and verified contract size remain
  outstanding. SHFE copper/aluminium, DCE iron ore and palladium are not
  implemented model markets. Lead is also absent.
- No actual CTA holdings or independent CTA estimate history is supplied, so
  actual-CTA estimation error is not measurable from these files.

## Proxy agreement, not predictive accuracy

Position-date joins use only the latest price at or before the report date,
within seven calendar days. Published reports become public later. These are
retrospective diagnostics, not trading signals based on unpublished reports.

| Market | 3y matched weeks | 3y level correlation | 3y weekly-change correlation | 1y level correlation |
|---|---:|---:|---:|---:|
| LME copper | 156 | 0.67 | 0.68 | 0.83 |
| COMEX copper | 156 | 0.58 | 0.68 | 0.59 |
| Aluminium | 157 | 0.58 | 0.62 | 0.08 |
| Nickel | 157 | 0.79 | 0.64 | 0.87 |
| Zinc | 156 | 0.76 | 0.68 | 0.43 |
| Platinum | 156 | 0.59 | 0.77 | −0.04 |
| Gold | 156 | 0.15 | 0.44 | −0.60 |
| Silver | 156 | 0.69 | 0.74 | 0.31 |

These are Pearson correlations of the model score with reported net/OI, or
their consecutive report-week changes. All-history level correlations conceal
recent instability: gold is 0.70 over all history but −0.60 over the last year;
platinum is 0.48 over all history but approximately zero over the last year.
Aluminium also has weak recent level agreement while its weekly-change
correlation is 0.67 over the last year. Model movement and fund level/bias are
different validation targets.

Every observed benchmark report in the last-year comparison window is net
long in all eight markets. An always-net-long classification therefore achieves
100% retrospective sign agreement in that window. High model sign agreement
alone is not evidence of forecasting skill. These overlapping, serially
correlated samples are not independent observations; no statistical significance,
causal result or out-of-sample performance claim is made. The one-year window is
a recent diagnostic, not a previously untouched holdout.

## Weekly validation and backtesting

**Completed:** weekly display retains each week's last observed daily model,
price and precomputed daily RSI, including the current partial week. Existing
sampling tests pass; the latest displayed partial-week point is 13 October.
Underlying daily model horizons and outputs are unchanged. Three-year charts
remain daily, with reports at their original weekly position dates. Full-history
charts use weekly display by default.

**Outstanding:** a separate weekly decision/rebalancing strategy has not been
validated. Lower displayed sign-flip counts reflect fewer plotted observations,
not measured lower turnover or superior returns. As an example, LME copper has
41 daily sign changes versus 15 changes among weekly displayed points over
three years; this is a display statistic only.

**Completed:** research backtest code has lagged exposure, turnover costs,
drawdowns, supplied-return support and safeguards; optional dashboard tests now
run rather than skip. Unverified continuous-proxy backtests remain blocked in
the UI. This run passed all **24 unit/UI tests** with no skips.

**Outstanding:** there is no verified executable futures performance result.
Contract-month settlements, a documented roll rule, actual availability timing,
held-contract return construction, costs/slippage, sizing and a locked
out-of-sample evaluation remain required. LME rolling 3M quotes are also not
a self-financing return series. Existing engine tests verify accounting and
timing behavior; they do not establish predictive skill. No new Sharpe or P&L
claim is made in this review.

## Repository work: completed versus outstanding

PRs #1–#7 are merged. PR #7 added gold/silver and weekly chart display. At review
time **PR #8 remained open**, adding zinc to reported comparisons. Main supported
nine price/model markets but six reported-comparison markets. This review's
proposed branch adds zinc and COMEX copper, taking comparison coverage to eight;
it overlaps PR #8's small zinc registration change. Neither PR #8 nor main was
merged or overwritten by this review.

New outputs: eight full-history plus eight three-year model/reported/price/RSI
charts; iron-ore full/three-year model/price charts with no invented reported
series; daily positions, weekly joins, coverage, recent-window diagnostics,
conditional shock tables and long-gap register. The dashboard code can select
all eight comparisons using these refreshed bundled inputs.

## Three highest-value next fixes

1. **Make refresh completeness visible and repeatable.** Consolidate price and
   position refreshes into a staged, atomic command with per-source retrieval
   manifests, revisions, report dates and actual publication times. Add freshness
   badges to every dashboard comparison and fail a run when a required source
   is missing. Use source publication schedules rather than a blanket age rule.
   Keep manual refresh as the default; add CI for the existing tests. Success:
   one command refreshes all configured markets and produces an explicit
   complete/partial status without silently mixing vintages.
2. **Validate the benchmark target and weekly decisions before tuning weights.**
   Separate structural fund long bias from changes in positioning, report rolling
   levels and changes plus a majority-sign baseline, and test release-aware,
   genuinely held-out periods. Investigate gold, platinum and aluminium first.
   Compare daily versus actual weekly rebalancing rather than plot sampling.
   Preserve a frozen baseline to avoid fitting noise. Success: documented
   validation target, lag rules and held-out improvement over simple baselines;
   no claim that managed money or investment funds equals CTA holdings.
3. **Build the contract/roll data needed for credible returns.** Start with one
   core market, storing settlements for dated contracts and adjacent roll legs,
   then construct adjusted signals separately from held-contract P&L. Reconcile
   the silver anomaly and nickel disruption; replace CME TIO with verified SGX
   data before claiming SGX accuracy. Extend to SHFE/DCE after the core path
   works. Success: audited lagged returns after trading/roll costs and a locked
   out-of-sample comparison against simple trend and market baselines.

## Reproduce and sources

From the repository root:

```bash
python scripts/fetch_research_price_proxies.py --output-dir dashboard/data --as-of 2026-10-13
python -m cta_models.cot --output dashboard/data/cftc_disaggregated_futures_only_hg_pl.csv --markets COMEX_HG NYMEX_PL
python -m cta_models.cot --output dashboard/data/cftc_disaggregated_futures_only_gc_si.csv --markets COMEX_GC COMEX_SI
python scripts/refresh_lme_recent.py --as-of 2026-10-13
python scripts/compare_reported_positions.py --output-dir output/comparisons
python scripts/run_proxy_models.py --output-dir output/iron_ore --markets SGX_IO62
python scripts/audit_coverage.py --output-dir output/audit
PYTHONPATH=src:. python -m unittest discover -s tests -v
```

- Repository: https://github.com/benj9971/cta_models
- Main reviewed: https://github.com/benj9971/cta_models/commit/35fb23701435601bb758f8baa919c027f4dd1306
- Open zinc PR at review: https://github.com/benj9971/cta_models/pull/8
- CFTC source API: https://publicreporting.cftc.gov/resource/72hh-3qpy.json
- LME report pages: https://www.lme.com/market-data/reports-and-data/commitments-of-traders
- Quote history example: https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash&year=2026
- Continuous quotes: Yahoo Finance chart API for HG=F, PL=F, GC=F, SI=F and TIO=F.

The historical source/proxy documentation retains its original dated snapshot;
this review records the newer refresh explicitly. Detailed CSVs and the run
manifest identify the observations used for this review.
