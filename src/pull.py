"""Download transaction-level contract data from USAspending, one slice per agency x FY.

Usage: python -m src.pull --all --workers 3   |   python -m src.pull --agency nasa --fy 2025
Each slice: count -> request download -> poll -> fetch zip -> count prime rows -> manifest row.
"""
import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from src import scope

RAW = Path("data/raw")
MANIFEST = Path("data/manifest.csv")
FIELDS = ["slice", "file_name", "prime_rows", "api_count", "zip_sha256", "pulled_at", "status"]


def fetch_json(url, body=None, timeout=300, attempts=6):
    """GET or POST JSON with backoff. USAspending times out and briefly 404s status URLs under load."""
    data = json.dumps(body).encode() if body is not None else None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == attempts - 1:
                raise
            wait = 20 * (i + 1)
            print(f"  retry {i + 1} in {wait}s: {e}", flush=True)
            time.sleep(wait)


def post(path, body):
    return fetch_json(scope.API + path, body)


def count_prime_rows(zpath):
    """Rows in Contracts_PrimeTransactions CSVs only; status total_rows also counts subawards."""
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if name.startswith("Contracts_PrimeTransactions"):
                n += sum(1 for _ in csv.reader(io.TextIOWrapper(z.open(name), encoding="utf-8"))) - 1
    return n


def check_rows(prime_rows, api_count):
    if prime_rows != api_count:
        raise ValueError(f"prime rows {prime_rows} != api count {api_count}")


def pull_slice(agency, fy, retries=1):
    name = f"{agency}-fy{fy}"
    f = scope.filters(agency, fy)
    cnt = post("download/count/", {"filters": f})
    if cnt.get("transaction_rows_gt_limit"):
        raise RuntimeError(f"{name}: {cnt['calculated_transaction_count']} rows exceeds the download cap")
    for attempt in range(retries + 1):
        job = post("download/transactions/", {"filters": f, "columns": scope.COLUMNS, "file_format": "csv"})
        while True:
            st = fetch_json(job["status_url"])
            if st.get("status") in ("finished", "failed"):
                break
            time.sleep(15)
        if st.get("status") == "finished":
            break
        print(f"{name}: job failed ({st.get('message')}), attempt {attempt + 1}", flush=True)
        time.sleep(600)
    else:
        raise RuntimeError(f"{name}: download failed after retries")
    zpath = RAW / f"{name}.zip"
    for i in range(4):
        try:
            urllib.request.urlretrieve(job["file_url"], zpath)
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == 3:
                raise
            time.sleep(30)
    rows = count_prime_rows(zpath)
    check_rows(rows, cnt["calculated_transaction_count"])
    return {"slice": name, "file_name": job["file_name"], "prime_rows": rows,
            "api_count": cnt["calculated_transaction_count"],
            "zip_sha256": hashlib.sha256(zpath.read_bytes()).hexdigest(),
            "pulled_at": datetime.now(UTC).isoformat(timespec="seconds"), "status": "ok"}


def done_slices():
    if not MANIFEST.exists():
        return set()
    return {r["slice"] for r in csv.DictReader(MANIFEST.open()) if r["status"] == "ok"}


def record(row):
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def run(todo, workers):
    RAW.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(pull_slice, a, fy): f"{a}-fy{fy}" for a, fy in todo}
        for fut, name in futs.items():
            try:
                row = fut.result()
                record(row)
                print(f"{name}: ok {row['prime_rows']} rows", flush=True)
            except Exception as e:  # noqa: BLE001 - one bad slice must not stop the others
                print(f"{name}: FAILED {e}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--agency", choices=list(scope.AGENCIES))
    ap.add_argument("--fy", type=int)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    done = done_slices()
    todo = scope.slices() if a.all else [(a.agency, a.fy)]
    run([s for s in todo if f"{s[0]}-fy{s[1]}" not in done], a.workers)


if __name__ == "__main__":
    main()
