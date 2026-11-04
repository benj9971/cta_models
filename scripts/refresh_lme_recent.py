"""Refresh recent public LME reports and 2026 Westmetall 3M quotes.

Preserves the existing historical archive and validates all downloads before
writing. Re-fetches overlapping recent reports to retain published revisions.
"""
import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor

import fetch_lme_cotr as cot

FILES = {
    "LME_CU": ("Cu", "lme_copper_3m_westmetall_2008-2026_import.csv"),
    "LME_AL": ("Al", "lme_aluminium_3m_westmetall_2008-2026_staged.csv"),
    "LME_NI": ("Ni", "lme_nickel_3m_westmetall_2008-2026_import.csv"),
    "LME_ZN": ("Zn", "lme_zinc_3m_westmetall_2008-2026_staged.csv"),
}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path("dashboard/data"))
    ap.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = ap.parse_args()
    discovered = cot.links()
    recent = []
    for item in discovered:
        text = re.search(r"(\d{1,2} [A-Za-z]+ \d{4})", item[3])
        if text is None:
            raise ValueError(f"Unrecognized report label: {item[3]}")
        when = datetime.strptime(text[1], "%d %B %Y").date()
        if args.as_of - timedelta(days=45) <= when <= args.as_of:
            recent.append(item)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(cot.parse, recent))
    staged = []
    for market, (symbol, filename) in FILES.items():
        path = args.data_dir / filename
        old = list(csv.DictReader(path.open()))
        url = f"https://www.westmetall.com/en/markdaten.php?action=table&field=LME_{symbol}_cash&year={args.as_of.year}"
        html = cot.get(url).decode("utf-8")
        if f"LME {dict(Cu='Copper',Al='Aluminium',Ni='Nickel',Zn='Zinc')[symbol]} 3-month" not in html:
            raise ValueError(f"Changed 3-month quote header: {url}")
        parsed = {}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = re.findall(r"<td[^>]*>\s*([^<]+?)\s*</td>", tr, re.S)
            if len(cells) != 4:
                continue
            try:
                when = datetime.strptime(cells[0].strip(), "%d. %B %Y").date()
            except ValueError:
                continue
            if when > args.as_of:
                continue
            quote = float(cells[2].strip().replace(",", ""))
            if quote <= 0 or when.weekday() >= 5:
                raise ValueError(f"Invalid quote: {market} {when} {quote}")
            if when.isoformat() in parsed:
                raise ValueError(f"Duplicate quote: {market} {when}")
            parsed[when.isoformat()] = dict(date=when.isoformat(), market=market,
                contract="3M_ROLLING", close=f"{quote:.2f}", signal_close=f"{quote:.2f}",
                source=old[0]['source'])
        combined = {r['date']: r for r in old}
        overlap = set(combined) & set(parsed)
        if len(overlap) < 100 or max(parsed) < max(combined):
            raise ValueError(f"Insufficient overlap or stale download: {market}")
        revisions = sum(float(combined[d]['close']) != float(parsed[d]['close']) for d in overlap)
        added = len(set(parsed) - set(combined))
        combined.update(parsed)
        staged.append((path, list(old[0]), [combined[d] for d in sorted(combined)]))
        report_path = args.data_dir / f"{market.lower()}_cotr_all_categories.csv"
        reports = list(csv.DictReader(report_path.open()))
        lookup = {(r['position_date'], r['category'], r['position_bucket']): r for r in reports}
        new = [r for group in results for r in group if r['market'] == market]
        if not new:
            raise ValueError(f"Missing recent reports: {market}")
        for r in new:
            if r['published_at_utc'][:10] > args.as_of.isoformat():
                raise ValueError(f"Report published after cutoff: {market}")
            k = (r['position_date'], r['category'], r['position_bucket'])
            if k not in lookup or r['published_at_utc'] >= lookup[k]['published_at_utc']:
                lookup[k] = r
        staged.append((report_path, cot.FIELDS, [lookup[k] for k in sorted(lookup)]))
        print(f"{market}: quote {max(parsed)}, {added} added, {revisions} overlapping revisions; report {max(k[0] for k in lookup)}", flush=True)
    for path, fields, rows in staged:
        temporary = path.with_suffix('.csv.tmp')
        with temporary.open('w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
        temporary.replace(path)
    print(f"Saved {len(staged)} files after all source downloads validated; {len(recent)} overlapping/new workbooks parsed")

if __name__ == '__main__':
    main()
