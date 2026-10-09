"""Fetch Yahoo continuous futures closes for *signal-only* research.

HG=F, GC=F, SI=F and PL=F represent vendor continuous COMEX/NYMEX futures. TIO=F is a
CME iron-ore future used only as a proxy for SGX iron ore; it is NOT SGX FEF.
Contract transitions and adjustment methodology are not verified. Never infer
executable P&L from these CSVs. Yahoo availability and usage terms may change.
"""

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MARKETS = {
    "COMEX_HG": ("HG=F", "USD/lb", 100.0),
    "NYMEX_PL": ("PL=F", "USD/troy oz", 1.0),
    "COMEX_GC": ("GC=F", "USD/troy oz", 1.0),
    "COMEX_SI": ("SI=F", "USD/troy oz", 1.0),
    "SGX_IO62": ("TIO=F", "USD/dmt", 1.0),
}


def fetch(market, as_of):
    ticker, unit, factor = MARKETS[market]
    start = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.combine(as_of + timedelta(days=1), datetime.min.time(),
                               tzinfo=timezone.utc).timestamp())
    query = urlencode({"period1": start, "period2": end, "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        chart = json.load(response)["chart"]
    if not chart["result"]:
        raise ValueError(chart["error"])
    result = chart["result"][0]
    metadata = result["meta"]
    if metadata.get("symbol") != ticker or metadata.get("currency") != "USD":
        raise ValueError(f"Unexpected ticker/currency: {metadata}")
    close = result["indicators"]["quote"][0]["close"]
    rows = []
    for timestamp, price in zip(result["timestamp"], close, strict=True):
        when = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        # Yahoo's older platinum history has repeated 1–3 month quote gaps.
        # Start the model-ready file where its daily coverage becomes regular.
        if price is None or when > as_of or (market == "NYMEX_PL" and when < date(2010, 1, 1)):
            continue
        value = float(price) * factor
        if value <= 0:
            raise ValueError(f"Nonpositive quote for {ticker} {when}")
        rows.append({"date": when.isoformat(), "market": market,
                     "contract": f"Yahoo continuous {ticker}; contract month unknown",
                     "close": round(value, 6), "signal_close": round(value, 6),
                     "source": f"YAHOO_{ticker}_UNVERIFIED_CONTINUOUS_SIGNAL_PROXY"})
    if len(rows) < 252 or len({r["date"] for r in rows}) != len(rows):
        raise ValueError(f"Incomplete or duplicate data: {ticker}")
    return rows, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True,
                        help="Include completed sessions through this YYYY-MM-DD date")
    parser.add_argument("--markets", nargs="+", choices=MARKETS, default=list(MARKETS),
                        help="Select markets to fetch; defaults to all configured proxies")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for market in args.markets:
        rows, meta = fetch(market, args.as_of)
        path = args.output_dir / f"{market.lower()}_yahoo_research_proxy.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"{market}: {len(rows)} quotes, {rows[0]['date']}–{rows[-1]['date']}; "
              f"latest {rows[-1]['close']}; Yahoo exchange {meta.get('exchangeName')}; "
              f"raw quote unit {MARKETS[market][1]}", flush=True)


if __name__ == "__main__":
    main()
