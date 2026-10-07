#!/usr/bin/env python3
"""Leak guard for the PUBLIC repo. Run before every push:

    python scripts/check_public.py           # tracked and addable files
    python scripts/check_public.py --dist    # the BUILT site and packet PDF (run after build.py --packet)

Fails (exit 1) if
  * a private path (CLAUDE.md, internal/, original photos, ...) is tracked or would be added,
  * a public file mentions private business terms (partnership model, rates, fam trip, ...), or
  * a public image still carries EXIF/GPS/XMP metadata (the hosts' photos were taken at home).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

PRIVATE_PATHS = re.compile(r"^(CLAUDE\.md|CLAUDE\.local\.md|internal/|\.env)|-original\.(jpe?g|png|heic|webp)$", re.I)

# Business terms that must never appear in public files.
FORBIDDEN = [
    (re.compile(r"(?<!great )\bcommissions?\b", re.I), "commission terms"),
    (re.compile(r"\bprofit[- ]?shar", re.I), "profit-share terms"),
    (re.compile(r"\bshare partner", re.I), "partnership model"),
    (re.compile(r"\bexclusivity\b", re.I), "exclusivity terms"),
    (re.compile(r"\bfam trip", re.I), "fam trip"),
    (re.compile(r"\bQ-(MODEL|FAM)-\d+", re.I), "internal-only question id"),
    (re.compile(r"\bmark-up\b|\bmarkups? (?:rate|of|on)\b|\bmargins? (?:rate|of|on)\b", re.I), "pricing margins"),
    # operator terms from the 2026-10-06 answers (private)
    (re.compile(r"KDV"), "Turkish VAT"),
    (re.compile(r"\bVAT\b"), "VAT"),
    (re.compile(r"\bnet (?:cost|price|rate)s?\b", re.I), "net pricing"),
    (re.compile(r"\b35 ?%"), "operator payment terms"),
    (re.compile(r"no-show", re.I), "operator cancellation terms"),
    (re.compile(r"\bcharter", re.I), "boat charter cost basis"),
    (re.compile(r"\bFOC\b"), "free-place terms"),
    (re.compile(r"\$ ?[78],?000"), "boat charter price"),
    (re.compile(r"180[–-]190"), "operator cost figures"),
]

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".j2", ".html", ".css", ".js", ".txt", ".json", ".svg", ""}


def candidate_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return sorted(set(out.split()))


def image_metadata(path: Path) -> list[str]:
    """Metadata blocks found in a WebP/JPEG/PNG file (dependency-free byte check)."""
    data = path.read_bytes()
    found = []
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(data):
            tag, size = data[i:i + 4], int.from_bytes(data[i + 4:i + 8], "little")
            if tag in (b"EXIF", b"XMP "):
                found.append(tag.decode().strip())
            i += 8 + size + (size & 1)
    elif data[:2] == b"\xff\xd8":
        if b"Exif\x00\x00" in data:
            found.append("EXIF")
        if b"http://ns.adobe.com/xap/" in data:
            found.append("XMP")
    elif data[:8] == b"\x89PNG\r\n\x1a\n" and (b"eXIf" in data or b"iTXtXML:com.adobe.xmp" in data):
        found.append("EXIF/XMP")
    return found


def scan_dist() -> int:
    """Scan dist/index.html and the text of every PDF in dist/ for forbidden terms."""
    dist = ROOT / "dist"
    texts: dict[str, str] = {}
    if (dist / "index.html").exists():
        texts["dist/index.html"] = (dist / "index.html").read_text(encoding="utf-8")
    pdfs = sorted(dist.glob("*.pdf"))
    if pdfs:
        try:
            import pymupdf
        except ImportError:
            print("pymupdf is needed to scan PDFs (pip install -r requirements-dev.txt)", file=sys.stderr)
            return 1
        for pdf in pdfs:
            with pymupdf.open(pdf) as doc:
                texts[f"dist/{pdf.name}"] = "\n".join(page.get_text() for page in doc)
    if not texts:
        print("nothing to scan in dist/: run build.py first", file=sys.stderr)
        return 1
    problems = []
    for name, text in texts.items():
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in FORBIDDEN:
                if pattern.search(line):
                    problems.append(f"{name}:{lineno}: {label}: {line.strip()[:100]}")
    if problems:
        print("LEAK CHECK FAILED (built output):", *problems, sep="\n  ", file=sys.stderr)
        return 1
    print(f"leak check OK (built output: {', '.join(texts)})")
    return 0


def main() -> int:
    if "--dist" in sys.argv[1:]:
        return scan_dist()
    problems: list[str] = []
    files = candidate_files()

    for path in files:
        if PRIVATE_PATHS.search(path):
            problems.append(f"PRIVATE FILE tracked or addable: {path}")

    for path in files:
        p = ROOT / path
        if p.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"} and p.is_file():
            meta = image_metadata(p)
            if meta:
                problems.append(f"{path}: image metadata present ({', '.join(meta)}); strip it before publishing")

    for path in files:
        p = ROOT / path
        if path == SELF or p.suffix not in TEXT_SUFFIXES or not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in FORBIDDEN:
                if pattern.search(line):
                    problems.append(f"{path}:{lineno}: {label}: {line.strip()[:100]}")

    if problems:
        print("LEAK CHECK FAILED:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    print(f"leak check OK ({len(files)} public files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
