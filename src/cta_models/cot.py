"""Fetch CFTC disaggregated futures-only managed-money positions.

This is a positioning benchmark, not a price series or a CTA position estimate.
Report dates are the Tuesday position dates; publication timestamps are not
provided in this export and must be attached before any predictive backtest.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

API = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
MARKETS = {"085692": "COMEX_HG", "076651": "NYMEX_PL"}
FIELDS = (
    "report_date_as_yyyy_mm_dd", "cftc_contract_market_code",
    "market_and_exchange_names", "open_interest_all",
    "m_money_positions_long_all", "m_money_positions_short_all",
    "m_money_positions_spread",
)
OUTPUT_FIELDS = (
    "market", "cftc_code", "report_date", "market_name", "open_interest",
    "managed_money_long", "managed_money_short", "managed_money_spreading",
    "managed_money_net", "managed_money_net_pct_oi", "retrieved_at_utc",
)


def normalize(records: list[dict], retrieved_at: str) -> list[dict]:
    result = []
    seen = set()
    for item in records:
        code = item["cftc_contract_market_code"]
        if code not in MARKETS:
            raise ValueError(f"Unexpected CFTC contract code {code}")
        date = item["report_date_as_yyyy_mm_dd"][:10]
        key = code, date
        if key in seen:
            raise ValueError(f"Duplicate market/report date: {key}")
        seen.add(key)
        long = int(item["m_money_positions_long_all"])
        short = int(item["m_money_positions_short_all"])
        spreading = int(item["m_money_positions_spread"])
        oi = int(item["open_interest_all"])
        if min(long, short, spreading, oi) < 0 or oi == 0:
            raise ValueError(f"Invalid positions/open interest: {key}")
        result.append({
            "market": MARKETS[code], "cftc_code": code, "report_date": date,
            "market_name": item["market_and_exchange_names"],
            "open_interest": oi, "managed_money_long": long,
            "managed_money_short": short, "managed_money_spreading": spreading,
            "managed_money_net": long - short,
            "managed_money_net_pct_oi": round((long - short) / oi, 8),
            "retrieved_at_utc": retrieved_at,
        })
    return sorted(result, key=lambda r: (r["report_date"], r["market"]))


def fetch(timeout: int = 30, page_size: int = 1000) -> list[dict]:
    records = []
    offset = 0
    while True:
        query = {
            "$select": ",".join(FIELDS),
            "$where": "cftc_contract_market_code in('085692','076651')",
            "$order": "report_date_as_yyyy_mm_dd,cftc_contract_market_code",
            "$limit": page_size, "$offset": offset,
        }
        with urlopen(API + "?" + urlencode(query), timeout=timeout) as response:
            page = json.load(response)
        if not isinstance(page, list):
            raise ValueError("Expected a list from CFTC API")
        records.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = normalize(fetch(), fetched)
    if not records or {r["market"] for r in records} != set(MARKETS.values()):
        raise ValueError("CFTC result missing one or both expected markets")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    for market in MARKETS.values():
        subset = [r for r in records if r["market"] == market]
        print(f"{market}: {len(subset)} weeks, {subset[0]['report_date']} to {subset[-1]['report_date']}; "
              f"latest managed-money net {subset[-1]['managed_money_net']:,} contracts")


if __name__ == "__main__":
    main()
