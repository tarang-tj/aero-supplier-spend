"""Number audit: every number in memo.md must be a `printed` value in memo_numbers.csv,
a year, or one of the externally sourced constants below."""
import csv
import re
from pathlib import Path

import pytest

MEMO = Path("memo.md")
NUMBERS = Path("data/out/memo_numbers.csv")
TOKEN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:%|B| million)?")
# Numbers that come from outside the dataset, each with its source.
EXTERNAL = {
    "1,800": "2023 DOJ/FTC Merger Guidelines, highly concentrated threshold",
    "$5,013 million": "Boeing 10-K for 2025, losses on five fixed-price development programs in 2024",
    "3364": "NAICS code, aerospace product and parts manufacturing",
    "6.302-1": "FAR section for only one responsible source",
}

# Names that contain digits but are not quantities.
NAMES = ("10-K", "L3Harris")


def memo_tokens(text):
    text = re.sub(r"\{[^}]*\}", " ", text)  # markdown attributes such as {width=62%}
    text = re.sub(r"FY\d{4}", " ", text)
    for name in NAMES:
        text = text.replace(name, " ")
    for k in EXTERNAL:
        text = text.replace(k, " ")
    return [t.rstrip(",.") for t in TOKEN.findall(text) if not re.fullmatch(r"(19|20)\d\d", t.rstrip(",."))]


def unsupported(text, printed):
    return [t for t in memo_tokens(text) if t not in printed]


@pytest.mark.skipif(not NUMBERS.exists(), reason="memo numbers not generated")
def test_every_memo_number_is_generated():
    printed = {r["printed"] for r in csv.DictReader(NUMBERS.read_text().splitlines())}
    assert unsupported(MEMO.read_text(), printed) == []


def test_audit_catches_a_fake_number():
    assert unsupported("Lockheed holds 61.2% of FY2025 spend.", {"43%"}) == ["61.2%"]
    assert unsupported("In FY2025 and 2024, 43% of spend.", {"43%"}) == []
