#!/usr/bin/env python3
"""Download the images listed in content/media.yaml and make responsive WebP versions.

    python scripts/fetch_images.py            # fetch anything missing
    python scripts/fetch_images.py --force    # re-fetch everything

For each image with a `file` and a Wikimedia Commons `source_url`, this downloads a
large rendition through the Commons API, strips metadata, and writes
assets/img/<file>-<width>.webp for every width in `widths`. It then records the
intrinsic size of the largest rendition (`width`/`height`) back into media.yaml so
the page can reserve space and avoid layout shift.

Only use images whose license allows reuse (CC BY, CC BY-SA, CC0, public domain), or
images from azimtours.com (owner's permission); credits.md is generated from media.yaml.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "content" / "media.yaml"
IMG = ROOT / "assets" / "img"
UA = {"User-Agent": "EphesianToursSiteBuild/0.1 (https://github.com/MIELA-LABS/ephesian-tours-website)"}


def quality(width: int) -> int:
    """Lower quality for larger renditions: they are shown big, where artifacts don't show."""
    return 74 if width <= 960 else 64 if width <= 1600 else 58


def commons_url(source_url: str, width: int) -> str:
    title = urllib.parse.unquote(source_url.rsplit("/wiki/", 1)[1]).replace("_", " ")
    q = urllib.parse.urlencode({
        "action": "query", "titles": title, "prop": "imageinfo",
        "iiprop": "url|size", "iiurlwidth": width, "format": "json",
    })
    req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers=UA)
    page = next(iter(json.load(urllib.request.urlopen(req, timeout=60))["query"]["pages"].values()))
    info = page["imageinfo"][0]
    return info.get("thumburl") if info["width"] > width else info["url"]


def fetch(url: str) -> Image.Image:
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    return img.convert("RGB")


def set_size(text: str, image_id: str, w: int, h: int) -> str:
    """Write width/height into the image's block in media.yaml, keeping comments intact."""
    block = re.compile(rf"(  - id: {re.escape(image_id)}\n(?:    .*\n)*?)(?=  - id: |\n|  #|\S|\Z)")
    m = block.search(text)
    if not m:
        raise SystemExit(f"media.yaml: block for '{image_id}' not found")
    body = re.sub(r"    (width|height): .*\n", "", m.group(1))
    body = re.sub(r"(    file: .*\n)", rf"\g<1>    width: {w}\n    height: {h}\n", body, count=1)
    return text[: m.start()] + body + text[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    IMG.mkdir(parents=True, exist_ok=True)
    media = yaml.safe_load(MEDIA.read_text(encoding="utf-8"))
    text = MEDIA.read_text(encoding="utf-8")
    for item in media["images"]:
        if not item.get("file"):
            print(f"skip {item['id']}: not sourced yet")
            continue
        widths = item.get("widths", [480, 960, 1600])
        outputs = [IMG / f"{item['file']}-{w}.webp" for w in widths]
        if all(o.exists() for o in outputs) and not args.force and item.get("width"):
            continue
        src = item.get("source_url", "")
        if "commons.wikimedia.org/wiki/" not in src:
            print(f"skip {item['id']}: download from {src} manually (not a Commons file page)")
            continue
        original = fetch(commons_url(src, max(widths)))
        for w, out in zip(widths, outputs):
            img = original if original.width <= w else original.resize(
                (w, round(original.height * w / original.width)), Image.LANCZOS)
            img.save(out, "WEBP", quality=quality(w), method=6)
        largest = Image.open(outputs[-1])
        text = set_size(text, item["id"], largest.width, largest.height)
        kb = sum(o.stat().st_size for o in outputs) // 1024
        print(f"{item['id']}: {len(outputs)} sizes, largest {largest.width}x{largest.height}, {kb} KB total")
    MEDIA.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
