#!/usr/bin/env python3
"""Generate every brand asset from one source of geometry:

    python scripts/make_brand.py

Writes
  templates/partials/_mark.svg.j2   inline mark (currentColor), used in header/hero/footer
  assets/img/logo.svg               mark + wordmark for light backgrounds (text as outlines)
  assets/img/logo-dark.svg          same, for dark backgrounds
  assets/img/favicon.svg            simplified mark on an Aegean tile (reads at 16px)
  assets/img/apple-touch-icon.png   180x180
  assets/img/og-image.jpg           1200x630 link-preview image (uses the hero photo once sourced)

The mark: an open arched doorway in classical stone, after the gate and the Library of
Celsus at Ephesus: entablature, paired columns, a keystoned arch, a door swung inward,
and light spilling over the threshold ("I have set before you an open door," Rev 3:8).

Needs requirements-dev.txt (Playwright, fonttools, uharfbuzz). Downloads Cormorant
Garamond (SIL Open Font License) into .cache/ to outline the wordmark.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (content loader, for brand name / hero image)

IMG = ROOT / "assets" / "img"
CACHE = ROOT / ".cache"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"
FONT_FILE = CACHE / "CormorantGaramond.ttf"

AEGEAN, AEGEAN_LIGHT = "#1F4E79", "#8DBBE6"
CHARCOAL, CREAM, LIMESTONE = "#2B2622", "#EEE7DA", "#F6F1E7"

# --- the mark (48 x 48, stroked with currentColor) -----------------------------------
MARK = [
    '<path d="M19.5 40h11l4.5 5h-20z" fill="currentColor" stroke="none" opacity=".25"/>',  # light
    '<path d="M5 8h38M7 11.5h34"/>',  # cornice + architrave
    '<path d="M9 15h4M35 15h4M10 15v25M12 15v25M36 15v25M38 15v25" stroke-width="1.6"/>',  # columns
    '<path d="M17 40V25a7 7 0 0 1 14 0v15"/>',  # arch
    '<path d="M22.6 17.2h2.8l-.5 2.6h-1.8z" fill="currentColor" stroke-width="1"/>',  # keystone
    '<path d="M17 40l3.5-2V26.3L17 25"/>',  # door leaf, swung inward
    '<path d="M5 40h38M3 44h42"/>',  # steps
]
# Simplified for 16-32px: single columns, heavier stroke.
MARK_SMALL = [
    '<path d="M6 9h36"/>',
    '<path d="M11 13v27M37 13v27"/>',
    '<path d="M17 40V25.5a7 7 0 0 1 14 0V40"/>',
    '<path d="M17 40l4-2.3V27l-4-1.5"/>',
    '<path d="M5 41h38"/>',
]
STROKE = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'


def mark_group(color: str, parts: list[str] = MARK, stroke_width: float = 2, transform: str = "") -> str:
    t = f' transform="{transform}"' if transform else ""
    return (
        f'<g color="{color}" fill="none" stroke="currentColor" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{t}>{"".join(parts)}</g>'
    )


# --- wordmark as outlines --------------------------------------------------------------


def load_font() -> tuple[TTFont, bytes]:
    if not FONT_FILE.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"downloading {FONT_URL}")
        urllib.request.urlretrieve(FONT_URL, FONT_FILE)
    font = instancer.instantiateVariableFont(TTFont(FONT_FILE), {"wght": 600})
    buf = io.BytesIO()
    font.save(buf)
    return TTFont(io.BytesIO(buf.getvalue())), buf.getvalue()


def text_path(text: str, size: float, x0: float, baseline: float) -> tuple[str, float]:
    """Shape `text` with HarfBuzz (kerning, ligatures) and return (svg path d, advance width)."""
    font, data = load_font()
    upem = font["head"].unitsPerEm
    hb_font = hb.Font(hb.Face(data))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()
    scale = size / upem
    pen = SVGPathPen(glyph_set)
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        tx = x0 + (x + pos.x_offset) * scale
        ty = baseline - pos.y_offset * scale
        glyph_set[order[info.codepoint]].draw(TransformPen(pen, (scale, 0, 0, -scale, tx, ty)))
        x += pos.x_advance
    return pen.getCommands(), x * scale


def logo_svg(mark_color: str, text_color: str, name: str) -> str:
    size, gap = 34.0, 11.0
    d, width = text_path(name, size, 48 + gap, 33.5)
    w = round(48 + gap + width + 2, 1)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 48" width="{w * 4:.0f}" height="192" '
        f'role="img" aria-label="{name}"><title>{name}</title>'
        f"{mark_group(mark_color)}"
        f'<path fill="{text_color}" d="{d}"/></svg>\n'
    )


def favicon_svg(rounded: bool = True) -> str:
    rx = ' rx="10"' if rounded else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        f'<rect width="48" height="48"{rx} fill="{AEGEAN}"/>'
        f'{mark_group(LIMESTONE, MARK_SMALL, 3.4, "translate(4.8 4.6) scale(.8)")}</svg>\n'
    )


def jinja_mark() -> str:
    return (
        '<svg class="{{ cls }}" viewBox="0 0 48 48" ' + STROKE +
        '{% if title %} role="img" aria-label="{{ title }}"{% else %} aria-hidden="true" focusable="false"{% endif %}>\n  '
        + "\n  ".join(MARK) + "\n</svg>\n"
    )


# --- raster assets via Playwright ------------------------------------------------------


def og_html(name: str, tagline: str, descriptor: str, domain: str, photo: Path | None) -> str:
    bg = (
        f"linear-gradient(180deg, rgb(14 18 24 / .35), rgb(14 18 24 / .82)), url('{photo.as_uri()}') center/cover"
        if photo
        else f"radial-gradient(circle at 75% 20%, #2E5E8C 0%, transparent 55%), linear-gradient(135deg, {AEGEAN} 0%, #10202F 100%)"
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Cormorant; src: url('{FONT_FILE.as_uri()}'); font-weight: 300 700; }}
html, body {{ margin: 0; width: 1200px; height: 630px; }}
body {{ background: {bg}; color: {LIMESTONE}; font-family: Cormorant, Georgia, serif;
  display: flex; flex-direction: column; justify-content: flex-end; padding: 64px 72px; box-sizing: border-box; }}
.lock {{ display: flex; align-items: center; gap: 22px; margin-bottom: 30px; }}
.lock svg {{ width: 92px; height: 92px; }}
.name {{ font-size: 62px; font-weight: 600; line-height: 1; }}
.desc {{ font: 400 24px/1.3 -apple-system, 'Segoe UI', sans-serif; opacity: .9; margin-top: 8px; }}
h1 {{ font-size: 76px; font-weight: 600; line-height: 1.02; margin: 0 0 26px; max-width: 900px; font-variant-numeric: lining-nums; }}
.foot {{ font: 600 22px -apple-system, 'Segoe UI', sans-serif; letter-spacing: .04em; opacity: .9; }}
</style></head><body>
<div class="lock"><svg viewBox="0 0 48 48">{mark_group(LIMESTONE)}</svg>
<div><div class="name">{name}</div><div class="desc">{descriptor}</div></div></div>
<h1>{tagline}</h1>
<div class="foot">Personally escorted from DFW · {domain}</div>
</body></html>"""


def render_rasters(c: dict) -> None:
    from playwright.sync_api import sync_playwright

    site, hero = c["site"], c["hero"]
    img = {i.id: i for i in c["images"]}[hero.image]
    photo = IMG / f"{img.file}-{img.widths[-1]}.webp" if img.ready else None
    if photo and not photo.exists():
        raise SystemExit(f"{photo} missing: run scripts/fetch_images.py first")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        og = CACHE / "og.html"  # loaded from a file so the local font and photo URLs resolve
        og.write_text(og_html(site.brand_name, hero.tagline, site.descriptor, site.domain, photo), encoding="utf-8")
        page.goto(og.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        page.screenshot(path=str(IMG / "og-image.jpg"), type="jpeg", quality=86)
        page = browser.new_page(viewport={"width": 180, "height": 180})
        page.set_content(f'<style>body{{margin:0}}svg{{width:180px;height:180px;display:block}}</style>{favicon_svg(rounded=False)}')
        page.screenshot(path=str(IMG / "apple-touch-icon.png"))
        browser.close()


def main() -> int:
    c = build.load_content()
    name = c["site"].brand_name
    IMG.mkdir(parents=True, exist_ok=True)
    (ROOT / "templates" / "partials" / "_mark.svg.j2").write_text(jinja_mark(), encoding="utf-8")
    (IMG / "logo.svg").write_text(logo_svg(AEGEAN, CHARCOAL, name), encoding="utf-8")
    (IMG / "logo-dark.svg").write_text(logo_svg(AEGEAN_LIGHT, CREAM, name), encoding="utf-8")
    (IMG / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    render_rasters(c)
    for f in ["logo.svg", "logo-dark.svg", "favicon.svg", "apple-touch-icon.png", "og-image.jpg"]:
        print(f"wrote assets/img/{f} ({(IMG / f).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
