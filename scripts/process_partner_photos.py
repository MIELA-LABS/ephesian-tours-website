#!/usr/bin/env python3
"""Export the partner (Azim Tours) tour photos as metadata-free WebP files for the gallery.

    python scripts/process_partner_photos.py [--src internal/photos/partner]

Originals stay outside the public repo (internal/photos/partner/, gitignored). For each photo
listed in content/media.yaml with a `file` under partner/, this writes
assets/img/partner/<name>-<width>.webp at the widths listed there (never wider than the
original) and records the largest size back into media.yaml.

Processing is limited to: converting to sRGB, cropping off white caption bars that some
originals carry at the bottom, and resizing. No retouching; faces are never altered.
Every output is a fresh image saved without EXIF, GPS, XMP or ICC data.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageCms, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "content" / "media.yaml"
OUT = ROOT / "assets" / "img"
QUALITY = 80


def to_srgb(img: Image.Image) -> Image.Image:
    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    img = img.convert("RGB")
    if icc:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        img = ImageCms.profileToProfile(img, src, ImageCms.createProfile("sRGB"), outputMode="RGB")
    return img


def crop_caption_bar(img: Image.Image) -> tuple[Image.Image, int]:
    """Remove a near-white caption bar at the bottom (rows whose median is almost white)."""
    gray = img.convert("L")
    w, h = gray.size
    bottom = h
    for y in range(h - 1, int(h * 0.75), -1):
        row = sorted(gray.crop((0, y, w, y + 1)).getdata())
        if row[len(row) // 2] < 235:  # first photographic row from the bottom
            bottom = y + 1
            break
    if bottom < h - 4:
        return img.crop((0, 0, w, bottom)), h - bottom
    return img, 0


def save_clean(img: Image.Image, path: Path, width: int) -> None:
    out = img if img.width == width else img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    clean = Image.new("RGB", out.size)
    clean.paste(out)
    clean.save(path, "WEBP", quality=QUALITY, method=6)  # no exif=, icc_profile=, xmp=


def set_size(text: str, image_id: str, w: int, h: int) -> str:
    block = re.compile(rf"(  - id: {re.escape(image_id)}\n(?:    .*\n)*?)(?=  - id: |\n|  #|\S|\Z)")
    m = block.search(text)
    body = re.sub(r"    (width|height): .*\n", "", m.group(1))
    body = re.sub(r"(    file: .*\n)", rf"\g<1>    width: {w}\n    height: {h}\n", body, count=1)
    return text[: m.start()] + body + text[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "internal" / "photos" / "partner")
    args = ap.parse_args()

    media = yaml.safe_load(MEDIA.read_text(encoding="utf-8"))
    text = MEDIA.read_text(encoding="utf-8")
    for item in media["images"]:
        file = item.get("file") or ""
        if not file.startswith("partner/"):
            continue
        name = file.split("/", 1)[1]
        originals = list(args.src.glob(f"{name}*-original.*")) or list(args.src.glob(f"{name[:2]}-*-original.*"))
        if len(originals) != 1:
            print(f"{item['id']}: expected one original for {name} in {args.src}, found {len(originals)}", file=sys.stderr)
            return 1
        img = to_srgb(Image.open(originals[0]))
        img, cropped = crop_caption_bar(img) if item.get("crop_caption_bar") else (img, 0)
        widths = [w for w in item["widths"] if w <= img.width]
        if not widths or widths[-1] < img.width and len(widths) < len(item["widths"]):
            widths.append(img.width)  # top size = original width, never upscaled
        (OUT / "partner").mkdir(parents=True, exist_ok=True)
        for w in widths:
            save_clean(img, OUT / f"{file}-{w}.webp", w)
        if widths != item["widths"]:
            text = re.sub(rf"(  - id: {item['id']}\n(?:    .*\n)*?    widths: )\[[^\]]*\]",
                          rf"\g<1>[{', '.join(map(str, widths))}]", text, count=1)
        largest = Image.open(OUT / f"{file}-{widths[-1]}.webp")
        text = set_size(text, item["id"], largest.width, largest.height)
        note = f", caption bar cropped ({cropped}px)" if cropped else ""
        print(f"{item['id']}: {originals[0].name} -> widths {widths}{note}")
    MEDIA.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
