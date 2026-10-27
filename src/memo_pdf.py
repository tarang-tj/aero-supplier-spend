"""Render memo.md -> docs/memo.html (pandoc) -> docs/memo.pdf (Chromium print), Letter, 11 pt.

Usage: python -m src.memo_pdf   (prints the PDF page count; the memo must fit on one page)
"""
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

CSS = """
body { font-family: Arial, Helvetica, sans-serif; font-size: 11pt; line-height: 1.32; color: #0b0b0b;
       background: #ffffff; max-width: 7.3in; margin: 0 auto; }
h1 { font-size: 15pt; margin: 0 0 4pt; }
p { margin: 0 0 6pt; }
img { display: block; margin: 2pt auto 0; max-width: 100%; }
figure { margin: 0; } figcaption { display: none; }
"""


def build(md=Path("memo.md"), html=Path("docs/memo.html"), pdf=Path("docs/memo.pdf")):
    body = subprocess.run(["pandoc", str(md), "-f", "markdown", "-t", "html5"], check=True,
                          capture_output=True, text=True).stdout
    html.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                    f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                    f"<title>Aerospace supplier spend memo</title><style>{CSS}</style></head>"
                    f"<body>{body}</body></html>")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html.resolve().as_uri())
        page.pdf(path=str(pdf), format="Letter", margin={"top": "0.5in", "bottom": "0.5in",
                                                        "left": "0.6in", "right": "0.6in"})
        browser.close()
    return len(PdfReader(str(pdf)).pages)


if __name__ == "__main__":
    print("memo pages:", build())
