"""Download public LME COT workbooks and preserve every position category.

Requires: requests, openpyxl, xlrd. Run from repository root:
python scripts/fetch_lme_cotr.py --output-dir dashboard/data
The CSV is long form: market x report date x five categories x three buckets.
Raw third-party XLS/XLSX files are not committed to the repository.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date
from io import BytesIO
from pathlib import Path
import re
import time
from urllib.parse import urljoin

import openpyxl
import requests
import xlrd

BASE = "https://www.lme.com"
PAGES = {"LME_CU": ("copper", "CA"), "LME_AL": ("aluminium", "AH"),
         "LME_ZN": ("lme-zinc", "ZS"), "LME_NI": ("lme-nickel", "NI")}
CATEGORIES = ("investment_firms_credit_institutions", "investment_funds",
              "other_financial_institutions", "commercial_undertakings",
              "emissions_compliance_operators")
BUCKETS = (("risk_reducing", 10, 13, 16), ("other", 11, 14, 17),
           ("total", 12, 15, 18))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; metals-cta-research/0.1)"}
LINK_RE = re.compile(r'<a href="([^"]+\.(?:xlsx|xls))" class="link-download">'
                     r'([^<]*Commitments of Traders Report[^<]*)</a>', re.I)
FIELDS = ("market", "lme_code", "position_date", "published_at_utc", "category",
          "position_bucket", "long_lots", "short_lots", "net_lots",
          "change_long_lots", "change_short_lots", "long_share_oi",
          "short_share_oi", "number_of_traders", "source_url")


def get(url):
    for attempt in range(4):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.content
        except (requests.RequestException, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def links():
    out = []
    for market, (slug, code) in PAGES.items():
        page = f"{BASE}/market-data/reports-and-data/commitments-of-traders/{slug}"
        matches = LINK_RE.findall(get(page).decode("utf-8"))
        if len(matches) < 100:
            raise ValueError(f"Unexpectedly few public reports for {market}: {len(matches)}")
        out.extend((market, code, urljoin(BASE, href), label)
                   for href, label in matches)
        print(f"{market}: discovered {len(matches)} linked workbooks", flush=True)
    return out


def workbook_rows(blob, url):
    if url.lower().endswith(".xlsx"):
        # Some public LME XLSX files declare an invalid/empty worksheet dimension.
        # Normal mode reads the populated columns despite that metadata.
        sh = openpyxl.load_workbook(BytesIO(blob), read_only=False, data_only=True).active
        return list(sh.values)
    if url.lower().endswith(".xls"):
        sh = xlrd.open_workbook(file_contents=blob).sheet_by_index(0)
        return [sh.row_values(i) for i in range(sh.nrows)]
    raise ValueError(f"Unrecognized workbook extension: {url}")


def parse(item):
    market, code, url, label = item
    rows = workbook_rows(get(url), url)
    def cell(r, c):
        return rows[r - 1][c - 1] if len(rows) >= r and len(rows[r - 1]) >= c else None
    if str(cell(6, 1)).strip() != code or str(cell(8, 6)).strip() != "Investment Funds":
        raise ValueError(f"Changed LME market/category layout: {url}")
    if str(cell(12, 3)).strip().lower() != "total":
        raise ValueError(f"Missing total row: {url}")
    report_date = str(cell(3, 1))[:10]
    date.fromisoformat(report_date)
    published_at = str(cell(4, 1))
    if not published_at.endswith("Z"):
        raise ValueError(f"Missing UTC publication timestamp: {url}")
    result = []
    for cat_idx, category in enumerate(CATEGORIES):
        col = 4 + cat_idx * 2
        if str(cell(9, col)).lower() != "long" or str(cell(9, col+1)).lower() != "short":
            raise ValueError(f"Changed direction columns: {url}")
        for bucket, row_pos, row_change, row_share in BUCKETS:
            lng, sht = float(cell(row_pos, col)), float(cell(row_pos, col+1))
            change_lng, change_sht = float(cell(row_change, col)), float(cell(row_change, col+1))
            share_lng, share_sht = float(cell(row_share, col)), float(cell(row_share, col+1))
            result.append(dict(market=market, lme_code=code, position_date=report_date,
                               published_at_utc=published_at, category=category,
                               position_bucket=bucket, long_lots=lng, short_lots=sht,
                               net_lots=round(lng-sht, 6), change_long_lots=change_lng,
                               change_short_lots=change_sht, long_share_oi=share_lng,
                               short_share_oi=share_sht,
                               number_of_traders=(cell(20, col) if bucket == "total" else ""),
                               source_url=url))
        a, b, total = result[-3:]
        if abs(a["long_lots"] + b["long_lots"] - total["long_lots"]) > .15 or abs(a["short_lots"] + b["short_lots"] - total["short_lots"]) > .15:
            raise ValueError(f"Position buckets do not sum: {url} {category}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    discovered = links()
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(parse, item): item for item in discovered}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                results.extend(future.result())
            except Exception as exc:
                errors.append((futures[future][2], str(exc)))
            if i % 100 == 0:
                print(f"Processed {i}/{len(discovered)} workbooks; errors {len(errors)}", flush=True)
    if errors:
        for url, issue in errors[:20]: print("ERROR", url, issue, flush=True)
        raise RuntimeError(f"{len(errors)} report(s) failed; refusing incomplete write")
    # Keep the latest published revision when several links cover one position date.
    latest = {}
    for row in results:
        key = (row["market"], row["position_date"], row["category"], row["position_bucket"])
        if key not in latest or row["published_at_utc"] > latest[key]["published_at_utc"]:
            latest[key] = row
    data = sorted(latest.values(), key=lambda r: (r["market"], r["position_date"], r["category"], r["position_bucket"]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for market in PAGES:
        with (args.output_dir / f"{market.lower()}_cotr_all_categories.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(r for r in data if r["market"] == market)
    for market in PAGES:
        dates = sorted({r["position_date"] for r in data if r["market"] == market})
        print(f"{market}: {len(dates)} dates, {dates[0]} to {dates[-1]}", flush=True)
    print(f"Saved {len(data)} category/bucket observations, {len(discovered)} linked files", flush=True)


if __name__ == "__main__":
    main()
