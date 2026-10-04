#!/usr/bin/env python3
"""Crop and export the hosts' portraits as metadata-free WebP files.

    python scripts/process_host_photos.py [--src internal/photos]

Originals live outside the public repo (internal/photos/, gitignored). Outputs, written to
assets/img/hosts/:
  <name>-480.webp, <name>-960.webp        4:5 portrait for the hosts cards and the packet
  hakan-avatar-112.webp, -168.webp        square face crop for the small round avatars

Every output is converted to sRGB and saved with NO metadata (no EXIF, GPS, XMP, or ICC).
Adjustments are limited to cropping and a light, global warm color balance; faces are not
retouched or altered.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "img" / "hosts"

# crop boxes in original pixels (left, top, right, bottom)
PHOTOS = {
    "hakan": {"file": "hakan-original.jpg", "crop": (0, 40, 1024, 1320), "warm": None},
    # tighter on face and shoulders to keep the porch background to a minimum
    "ece": {"file": "ece-original.jpg", "crop": (330, 340, 1424, 1708), "warm": (1.03, 1.0, 0.96)},
}
AVATAR = {"from": "hakan", "crop": (190, 140, 834, 784)}  # square around the face
WIDTHS = [480, 960]
AVATAR_WIDTHS = [112, 168]


def to_srgb(img: Image.Image) -> Image.Image:
    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if icc:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        img = ImageCms.profileToProfile(img, src, ImageCms.createProfile("sRGB"), outputMode="RGB")
    return img


def warm(img: Image.Image, gains: tuple[float, float, float] | None) -> Image.Image:
    if not gains:
        return img
    channels = [c.point(lambda v, g=g: min(255, round(v * g))) for c, g in zip(img.split(), gains)]
    return Image.merge("RGB", channels)


def save_clean(img: Image.Image, path: Path, width: int, quality: int = 82) -> None:
    out = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    clean = Image.new("RGB", out.size)  # fresh image: carries no info/metadata at all
    clean.paste(out)
    clean.save(path, "WEBP", quality=quality, method=6)  # no exif=, icc_profile=, or xmp=


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "internal" / "photos")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    prepared: dict[str, Image.Image] = {}
    for name, spec in PHOTOS.items():
        src = args.src / spec["file"]
        if not src.exists():
            print(f"missing {src}", file=sys.stderr)
            return 1
        base = warm(to_srgb(Image.open(src)), spec["warm"])
        prepared[name] = base
        portrait = base.crop(spec["crop"])
        for w in WIDTHS:
            save_clean(portrait, OUT / f"{name}-{w}.webp", w)
        print(f"{name}: portrait {portrait.width}x{portrait.height} -> {', '.join(f'{name}-{w}.webp' for w in WIDTHS)}")

    face = prepared[AVATAR["from"]].crop(AVATAR["crop"])
    for w in AVATAR_WIDTHS:
        save_clean(face, OUT / f"{AVATAR['from']}-avatar-{w}.webp", w)
    print(f"avatar: {face.width}x{face.height} -> {AVATAR['from']}-avatar-{{{','.join(map(str, AVATAR_WIDTHS))}}}.webp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
