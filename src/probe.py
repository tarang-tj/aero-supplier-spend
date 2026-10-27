"""Boot probe for the static page: 1440 and 375 px, no console errors, no horizontal scroll,
every image and same-site link resolves. Usage: python -m src.probe [url-or-path]
Exits 1 on any failure; writes screenshots to data/probe/.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SHOTS = Path("data/probe")


def probe(target):
    url = target if target.startswith("http") else Path(target).resolve().as_uri()
    failures = []
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1440, 375):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("console", lambda m, e=errors: m.type == "error" and e.append(m.text))
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            page.goto(url, wait_until="load")
            failures += [f"{width}px console: {e}" for e in errors]
            if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
                failures.append(f"{width}px: horizontal scroll")
            broken = page.evaluate("[...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)")
            failures += [f"{width}px broken image {b}" for b in broken]
            page.screenshot(path=str(SHOTS / f"page-{width}.png"), full_page=True)
            page.close()
        links = []
        page = browser.new_page()
        page.goto(url)
        links = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href)"
                              ".filter(h => h.startsWith(location.origin) || h.startsWith('file:'))")
        for href in set(links):
            if href.startswith("file:"):
                if not Path(href.removeprefix("file://").split("#")[0]).exists():
                    failures.append(f"missing file link {href}")
            else:
                r = page.request.get(href)
                if r.status >= 400:
                    failures.append(f"link {href} -> {r.status}")
        browser.close()
    return failures


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "docs/index.html"
    failures = probe(target)
    for f in failures:
        print("FAIL", f)
    print("probe:", "FAIL" if failures else "OK", target)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
