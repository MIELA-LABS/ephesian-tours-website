#!/usr/bin/env python3
"""Render the pastor's info packet PDF from the same content as the site.

    python build.py --packet          # normal use: builds the site, then the packet into dist/
    python scripts/make_packet.py     # packet only (writes dist/<contact.packet_file>)

templates/packet.html.j2 is rendered with the site's content and printed to a US Letter
PDF by Chromium (Playwright), with the site's fonts, colors, and logo. Nothing is typed into
the packet by hand, so it cannot drift from the site:
  * season prices are shown unless still pending (then booking.pricing_title, "Pricing on request")
  * other pending terms read packet.to_be_confirmed; no "Sample" badges appear
  * while site.preview_mode is on, the footer reads "Preview edition · <Month Year>"
The build fails if the web fonts did not load, rather than silently using fallbacks.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

IMG = ROOT / "assets" / "img"
CACHE = ROOT / ".cache"

FOOTER = """
<div style="width:100%;padding:0 0.65in;display:flex;justify-content:space-between;
  font-family:'Helvetica Neue',Arial,sans-serif;font-size:7.5pt;color:#5A5048;">
  <span>{left}</span><span>{center}</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>"""


def make_packet(c: dict[str, Any], out: Path) -> int:
    """Render the packet to `out`; returns the page count. The packet always shows
    site.base_url (the public domain), not the address of a preview deploy."""
    from playwright.sync_api import sync_playwright

    images = {i.id: i for i in c["images"]}

    def img_src(image_id: str, width: int | None = None) -> str:
        """Print-quality JPEG copy of a site image. Chromium embeds JPEGs as-is, whereas
        WebP images would be stored uncompressed and make the PDF ten times larger."""
        from PIL import Image

        i = images[image_id]
        w = width if width in i.widths else i.widths[-1]
        webp = IMG / f"{i.file}-{w}.webp"
        if not webp.exists():
            raise build.BuildError(f"packet: missing image {webp.relative_to(ROOT)}")
        jpg = CACHE / "packet-img" / f"{i.file.replace('/', '-')}-{w}.jpg"
        if not jpg.exists() or jpg.stat().st_mtime < webp.stat().st_mtime:
            jpg.parent.mkdir(parents=True, exist_ok=True)
            Image.open(webp).convert("RGB").save(jpg, "JPEG", quality=82, optimize=True, progressive=True)
        return jpg.as_uri()

    used = [c["hero"].image] + [j.image for j in c["journeys"]]
    credits, seen = [], set()
    for image_id in used:
        i = images[image_id]
        if i.source_url and image_id not in seen:  # our own photos need no credit line
            seen.add(image_id)
            credits.append(i)

    base_url = str(c["site"].base_url).rstrip("/") + "/"
    ctx = build.template_context(c, base_url) | {
        "img_src": img_src,
        "packet_credits": credits,
    }
    html = build.jinja_env().get_template("packet.html.j2").render(**ctx)
    CACHE.mkdir(exist_ok=True)
    src = CACHE / "packet.html"  # a file URL, so local images resolve
    src.write_text(html, encoding="utf-8")

    edition = ""
    if c["site"].preview_mode:
        edition = f"{c['packet'].edition_label} · {date.today():%B %Y}"
    footer = FOOTER.format(left=edition, center=base_url.rstrip("/").removeprefix("https://"))

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(src.as_uri(), wait_until="networkidle")
        ok = page.evaluate(
            """async () => { await document.fonts.ready;
                return document.fonts.check('600 20px "Cormorant Garamond"') &&
                       document.fonts.check('400 12px "Source Sans 3"'); }"""
        )
        if not ok:
            browser.close()
            raise build.BuildError("packet: web fonts did not load (check network access to Google Fonts)")
        page.pdf(
            path=str(out),
            prefer_css_page_size=True,
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=footer,
        )
        browser.close()
    data = out.read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def main() -> int:
    c = build.load_content()
    out = build.DIST / c["contact"].packet_file
    pages = make_packet(c, out)
    print(f"wrote {out.relative_to(ROOT)} ({pages} pages, {out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
