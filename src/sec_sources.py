"""Fetch each major prime's latest 10-K Exhibit 21 (list of subsidiaries) from SEC EDGAR.

These are the primary sources behind crosswalk rows with basis = subsidiary.
Usage: python -m src.sec_sources   -> data/sources/<ticker>-ex21.txt and data/sources/index.csv
"""
import csv
import html
import json
import re
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "aero-supplier-spend research (github.com/tarang-tj/aero-supplier-spend)"}
OUT = Path("data/sources")
CIKS = {"LMT": 936468, "RTX": 101829, "LHX": 202058, "BA": 12927, "NOC": 1133421,
        "GD": 40533, "TXT": 217346, "HON": 773840, "GE": 40545, "LDOS": 1336920, "KBR": 1357615}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def latest_10k(cik):
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    rec = sub["filings"]["recent"]
    for form, acc, date in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], strict=True):
        if form == "10-K":
            return acc.replace("-", ""), date
    raise LookupError(f"no 10-K for {cik}")


def ex21_url(cik, acc):
    idx = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"))
    for item in idx["directory"]["item"]:
        if re.search(r"ex-?21|exhibit21|ex21", item["name"], re.IGNORECASE):
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{item['name']}"
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker, cik in CIKS.items():
        acc, date = latest_10k(cik)
        url = ex21_url(cik, acc)
        if url:
            text = html.unescape(re.sub(r"<[^>]+>", " ", get(url).decode("utf-8", "replace")))
            (OUT / f"{ticker}-ex21.txt").write_text(re.sub(r"\s+", " ", text))
        rows.append({"ticker": ticker, "cik": cik, "filed": date, "ex21_url": url or "NOT FOUND"})
        print(rows[-1])
        time.sleep(0.3)  # SEC fair-access limit is 10 req/s
    with (OUT / "index.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
