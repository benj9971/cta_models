# CTA positioning source bundle | 4 November 2026

The Python model, Streamlit metals dashboard and November chart scripts share the same engine. ES and NQ run as chart prototypes, not Streamlit selections.

## Run from the extracted folder (Python 3.10+)

    python -m pip install -e ".[dashboard,data]"
    python nov/render.py

Open nov/CTA_3Y_2026-11-04.html. The renderer uses the included price and report snapshots offline and also writes eleven PNGs and snapshot.csv. Do not run equity.py first unless you want to fetch the vintage again; providers can revise historical quotes.

## Dashboard

    python -m streamlit run dashboard/app.py

## Files

- src/cta_models/model.py: daily 20/60/120/252-session score and volatility scaling.
- dashboard/data/: November input snapshot, shared by the dashboard and exporter.
- scripts/: price/report fetchers, chart exporters and diagnostics.
- nov/equity.py: ES/NQ continuous quote and CFTC TFF leveraged-fund prototype pulls.
- nov/CME_*_reported.csv: equity report observations for offline rendering.
- nov/render.py: all eleven charts. Its title, dates and filenames identify the November run.
- tests/: model and dashboard checks.

The equity fetcher is pinned to the November snapshot's date limits. For another vintage, change the price and report cutoffs and update the renderer labels. Dashboard/data documentation may describe older snapshots. US vendor quotes dated 3 November are preliminary; the LME and iron-ore price inputs stop on 2 November.
