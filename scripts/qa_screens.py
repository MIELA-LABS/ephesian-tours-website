#!/usr/bin/env python3
"""QA screenshots of the built site (run `python build.py` first).

    python scripts/qa_screens.py                       # full pages: 375/768/1440 px x light/dark
    python scripts/qa_screens.py --open-itinerary      # also expand the first itinerary
    python scripts/qa_screens.py --selector .site-header --widths 375 1440   # crop to an element

Serves dist/ on a local port, captures with Playwright (Chromium), and reports
horizontal overflow and console errors. Screenshots go to qa/ (gitignored).
Requires requirements-dev.txt and `python -m playwright install chromium`.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def serve() -> tuple[socketserver.TCPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(DIST))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--widths", type=int, nargs="+", default=[375, 768, 1440])
    ap.add_argument("--themes", nargs="+", default=["light", "dark"], choices=["light", "dark"])
    ap.add_argument("--selector", help="screenshot only this element")
    ap.add_argument("--open-itinerary", action="store_true", help="expand the first itinerary (loads its map)")
    ap.add_argument("--out", type=Path, default=ROOT / "qa")
    args = ap.parse_args()

    if not (DIST / "index.html").exists():
        print("dist/index.html not found: run `python build.py` first", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    server, port = serve()
    problems: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for theme in args.themes:
            for width in args.widths:
                page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=theme,
                                        device_scale_factor=2 if width < 800 else 1)
                errors: list[str] = []
                page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
                page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.evaluate("document.querySelectorAll('.reveal').forEach(e => e.classList.add('is-visible'))")
                # QA only: load every lazy image now, so full-page captures show them
                page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => { i.loading = 'eager'; })")
                # scroll through the page so lazy images load, then return to the top
                page.evaluate("""async () => {
                  for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }
                  window.scrollTo(0, 0);
                }""")
                page.wait_for_load_state("networkidle")
                page.wait_for_function("[...document.images].filter(i => i.getClientRects().length).every(i => i.complete)", timeout=20000)
                if args.open_itinerary:
                    page.evaluate("document.querySelector('details.itinerary').open = true")
                    page.wait_for_timeout(2500)  # Leaflet + tiles
                page.wait_for_timeout(300)

                overflow = page.evaluate(
                    """() => {
                      const w = document.documentElement.clientWidth;
                      return [...document.querySelectorAll('body *')]
                        .filter(el => { const r = el.getBoundingClientRect(); return r.width && r.right > w + 1; })
                        .filter(el => !el.closest('.leaflet-container, .form__hp, .skip-link, .visually-hidden'))
                        // content inside its own horizontal scroller (e.g. the gallery track) is meant to extend off-screen
                        .filter(el => { for (let a = el.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return false; } return true; })
                        .slice(0, 5).map(el => el.tagName.toLowerCase() + '.' + [...el.classList].join('.'));
                    }"""
                )
                if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                    problems.append(f"{width}px {theme}: the page scrolls horizontally")
                if overflow:
                    problems.append(f"{width}px {theme}: horizontal overflow from {', '.join(overflow)}")
                problems += [f"{width}px {theme}: console: {e}" for e in errors]

                name = f"{args.selector.strip('.#').replace(' ', '_') if args.selector else 'page'}-{width}-{theme}.png"
                path = args.out / name
                if args.selector:
                    page.locator(args.selector).first.screenshot(path=str(path))
                else:
                    page.screenshot(path=str(path), full_page=True)
                print(f"saved {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
                page.close()
        browser.close()
    server.shutdown()

    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
