"""Refresh LME three-month quotes from Westmetall into model-ready CSVs.

Needs only westmetall.com (lme.com is not required), so it works from the
scheduled metal watches. For each market it starts from the committed history
in dashboard/data, re-downloads the current year (and the previous year in
January, or every year back to 2008 when no history exists or --full is set),
lets downloaded quotes replace overlapping archive rows (published revisions),
validates the result and writes <output-dir>/<market>_westmetall_3m.csv for
scripts/run_proxy_models.py. With --update-archive it also rewrites the
committed history file.

The quote is Westmetall's "LME <metal> 3-month" column: a published daily
rolling three-month quote, not an executable closing price or a futures P&L.

Example:
    python scripts/update_lme_3m.py --output-dir /tmp/px --as-of 2026-11-06 --markets LME_CU LME_PB
"""

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dashboard" / "data"
FIRST_YEAR = 2008
# Westmetall field symbol, metal name in the column header, committed history file
MARKETS = {
    "LME_CU": ("Cu", "Copper", "lme_copper_3m_westmetall_2008-2026_import.csv"),
    "LME_AL": ("Al", "Aluminium", "lme_aluminium_3m_westmetall_2008-2026_staged.csv"),
    "LME_NI": ("Ni", "Nickel", "lme_nickel_3m_westmetall_2008-2026_import.csv"),
    "LME_ZN": ("Zn", "Zinc", "lme_zinc_3m_westmetall_2008-2026_staged.csv"),
    "LME_PB": ("Pb", "Lead", "lme_lead_3m_westmetall_2008-2026_staged.csv"),
}
FIELDS = ("date", "market", "contract", "close", "signal_close", "source")
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>\s*([^<]*?)\s*</td>", re.S)
# Known genuine gaps: LME nickel trading was suspended 8 March 2022 after the
# squeeze and no three-month quote was published until 28 March.
KNOWN_GAPS = {("LME_NI", "2022-03-07", "2022-03-28")}


def get(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                return r.read().decode("utf-8")
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def year_quotes(market, year, as_of):
    symbol, metal, _ = MARKETS[market]
    url = (f"https://www.westmetall.com/en/markdaten.php?action=table"
           f"&field=LME_{symbol}_cash&year={year}")
    html = get(url)
    if f"LME {metal} 3-month" not in html:
        raise ValueError(f"3-month column missing or renamed: {url}")
    out = {}
    for tr in ROW_RE.findall(html):
        cells = CELL_RE.findall(tr)
        if len(cells) != 4:
            continue
        try:
            when = datetime.strptime(cells[0].strip(), "%d. %B %Y").date()
        except ValueError:
            continue
        raw = cells[2].strip().replace(",", "")
        # Skip absent quotes, future dates and Westmetall's occasional weekend
        # repeat of Friday's quote; never fill or interpolate.
        if when > as_of or when.weekday() >= 5 or raw in ("", "-"):
            continue
        quote = float(raw)
        if quote <= 0:
            raise ValueError(f"Nonpositive quote: {market} {when} {quote}")
        if when.isoformat() in out:
            raise ValueError(f"Duplicate quote: {market} {when}")
        out[when.isoformat()] = quote
    return out


def refresh(market, as_of, full=False):
    _, _, filename = MARKETS[market]
    path = ARCHIVE / filename
    archive = {}
    if path.exists() and not full:
        archive = {r["date"]: float(r["close"]) for r in csv.DictReader(path.open())}
    if archive:
        years = sorted({as_of.year, (as_of - timedelta(days=31)).year})
    else:
        years = list(range(FIRST_YEAR, as_of.year + 1))
    fetched = {}
    for year in years:
        fetched.update(year_quotes(market, year, as_of))
    if not fetched:
        raise ValueError(f"No quotes downloaded for {market}")
    overlap = set(archive) & set(fetched)
    if archive and len(overlap) < 20:
        raise ValueError(f"Too little overlap with the archive for {market}: {len(overlap)}")
    revisions = sum(abs(archive[d] - fetched[d]) > 1e-9 for d in overlap)
    added = len(set(fetched) - set(archive))
    combined = {**archive, **fetched}
    dates = sorted(combined)
    if not archive:
        # The 2008 tables can hold an isolated early fragment before a long gap
        # (zinc, aluminium). Start after the last gap longer than 10 days.
        start = 0
        for i in range(1, len(dates)):
            gap = date.fromisoformat(dates[i]) - date.fromisoformat(dates[i - 1])
            if gap.days > 10:
                start = i
        dates = dates[start:]
    for a, b in zip(dates, dates[1:]):
        if (date.fromisoformat(b) - date.fromisoformat(a)).days > 10 and (market, a, b) not in KNOWN_GAPS:
            raise ValueError(f"Gap over 10 days in {market}: {a} to {b}")
    if len(dates) < 300:
        raise ValueError(f"Too few quotes for the 252-session model: {market} {len(dates)}")
    if (as_of - date.fromisoformat(dates[-1])).days > 7:
        raise ValueError(f"Stale download for {market}: latest {dates[-1]}")
    rows = [dict(date=d, market=market, contract="3M_ROLLING", close=f"{combined[d]:.2f}",
                 signal_close=f"{combined[d]:.2f}", source=f"WESTMETALL_{market}_3M")
            for d in dates]
    return rows, path, added, revisions


def write(path, rows):
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--as-of", type=date.fromisoformat, required=True)
    ap.add_argument("--markets", nargs="+", choices=MARKETS, default=list(MARKETS))
    ap.add_argument("--full", action="store_true", help="Ignore the archive and re-download 2008 onwards")
    ap.add_argument("--update-archive", action="store_true", help="Also rewrite dashboard/data history")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for market in args.markets:
        rows, archive_path, added, revisions = refresh(market, args.as_of, args.full)
        write(args.output_dir / f"{market.lower()}_westmetall_3m.csv", rows)
        if args.update_archive:
            write(archive_path, rows)
        print(f"{market}: {len(rows)} quotes {rows[0]['date']} to {rows[-1]['date']}; "
              f"latest 3M {rows[-1]['close']} USD/t; {added} added, {revisions} revised vs archive",
              flush=True)


if __name__ == "__main__":
    main()
