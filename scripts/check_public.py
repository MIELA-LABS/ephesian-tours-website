#!/usr/bin/env python3
"""Leak guard for the PUBLIC repo. Run before every push:

    python scripts/check_public.py           # tracked and addable files
    python scripts/check_public.py --dist    # the BUILT site and packet PDF (run after build.py --packet)
    python scripts/check_public.py --staged  # lines added in the staged commit (run before git commit)

Fails (exit 1) if
  * a private path (CLAUDE.md, internal/, original photos, ...) is tracked or would be added,
  * a public image still carries EXIF/GPS/XMP metadata, or
  * a public file, the built site, or the PDF contains a private term or figure.

The private terms and figures are deliberately NOT in this file (it is public). They are loaded
from internal/private-patterns.txt (gitignored) or, in CI, from the GitHub Actions secret
LEAK_PRIVATE_PATTERNS. The check refuses to run without them. Reports name the file and line
only, never the matched text, because CI logs of a public repo are public too.
"""

from __future__ import annotations

import html as html_lib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

PRIVATE_PATHS = re.compile(r"^(CLAUDE\.md|CLAUDE\.local\.md|internal/|\.env)|-original\.(jpe?g|png|heic|webp)$", re.I)
PRIVATE_LIST_FILE = ROOT / "internal" / "private-patterns.txt"
PRIVATE_LIST_ENV = "LEAK_PRIVATE_PATTERNS"

# layout values are not figures: "1100px", srcset "1400w", width="1330", height: 1330
LAYOUT_AFTER = re.compile(r"\s*(?:px|w\b|rem\b|em\b|vw\b|%)")
LAYOUT_BEFORE = re.compile(r"(?:width|height)\s*[:=]\s*[\"']?\s*$", re.I)

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".j2", ".html", ".css", ".js", ".txt", ".json", ".svg", ""}


class PrivateList:
    """Numbers and regular expressions loaded from the private list."""

    def __init__(self, raw: str) -> None:
        self.numbers: list[str] = []
        self.patterns: list[re.Pattern[str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("re-cs:"):
                self.patterns.append(re.compile(line[6:].strip()))
            elif line.startswith("re:"):
                self.patterns.append(re.compile(line[3:].strip(), re.I))
            else:
                self.numbers += [t for t in line.replace(",", "").split() if t.isdigit()]
        if not (self.numbers or self.patterns):
            sys.exit(f"LEAK CHECK CANNOT RUN: no private list ({PRIVATE_LIST_FILE.relative_to(ROOT)} or ${PRIVATE_LIST_ENV})")
        alts = "|".join(f"{n[:-3]},?{n[-3:]}" if len(n) > 3 else n for n in sorted(set(self.numbers)))
        # whole numbers only, with or without a thousands comma; not inside longer numbers,
        # decimals, or a phone-number tail such as 555-1234
        self.number_re = re.compile(rf"(?<![\d,.])(?<!\d-)(?:{alts})(?![\d])(?!,\d)(?!\.\d)") if alts else None

    def hits(self, line: str) -> int:
        n = sum(1 for p in self.patterns if p.search(line))
        if self.number_re:
            for m in self.number_re.finditer(line):
                if not (LAYOUT_AFTER.match(line, m.end()) or LAYOUT_BEFORE.search(line[: m.start()])):
                    n += 1
        return n


def load_private_list() -> PrivateList:
    raw = os.environ.get(PRIVATE_LIST_ENV, "")
    if not raw.strip() and PRIVATE_LIST_FILE.exists():
        raw = PRIVATE_LIST_FILE.read_text(encoding="utf-8")
    return PrivateList(raw)


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


def scan_text(name: str, text: str, private: PrivateList) -> list[str]:
    return [f"{name}:{n}: private term or figure" for n, line in enumerate(text.splitlines(), 1) if private.hits(line)]


def report(problems: list[str], ok: str) -> int:
    if problems:
        print("LEAK CHECK FAILED:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    print(f"leak check OK ({ok})")
    return 0


def scan_dist(private: PrivateList) -> int:
    """Scan dist/index.html and the text of every PDF in dist/."""
    dist = ROOT / "dist"
    texts: dict[str, str] = {}
    if (dist / "index.html").exists():
        page = (dist / "index.html").read_text(encoding="utf-8")
        # one text element per line: inline tags joined, block tags split, so proximity rules
        # look within a single element rather than a raw HTML line
        page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "\n", page)
        page = re.sub(r"(?i)</?(?:a|strong|em|b|i|span|cite|abbr|small)\b[^>]*>", "", page)
        page = re.sub(r"<[^>]+>", "\n", page)
        texts["dist/index.html"] = html_lib.unescape(page)
    pdfs = sorted(dist.glob("*.pdf"))
    if pdfs:
        try:
            import pymupdf
        except ImportError:
            print("pymupdf is needed to scan PDFs (pip install -r requirements-dev.txt)", file=sys.stderr)
            return 1
        for pdf in pdfs:
            with pymupdf.open(pdf) as doc:
                texts[f"dist/{pdf.name}"] = "\n".join(p.get_text() for p in doc)
    if not texts:
        print("nothing to scan in dist/: run build.py first", file=sys.stderr)
        return 1
    problems = [p for name, text in texts.items() for p in scan_text(name, text, private)]
    return report(problems, f"built output: {', '.join(texts)}")


def scan_staged(private: PrivateList) -> int:
    """Scan the lines added in the staged commit (git diff --cached)."""
    diff = subprocess.run(["git", "diff", "--cached", "-U0"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    problems, current = [], "?"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and private.hits(line):
            problems.append(f"{current}: private term or figure in an added line")
    return report(problems, "staged changes")


def main() -> int:
    private = load_private_list()
    if "--dist" in sys.argv[1:]:
        return scan_dist(private)
    if "--staged" in sys.argv[1:]:
        return scan_staged(private)

    problems: list[str] = []
    files = candidate_files()
    for path in files:
        p = ROOT / path
        if PRIVATE_PATHS.search(path):
            problems.append(f"PRIVATE FILE tracked or addable: {path}")
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"}:
            meta = image_metadata(p)
            if meta:
                problems.append(f"{path}: image metadata present ({', '.join(meta)}); strip it before publishing")
        elif p.suffix in TEXT_SUFFIXES:
            problems += scan_text(path, p.read_text(encoding="utf-8", errors="ignore"), private)
    return report(problems, f"{len(files)} public files scanned")


if __name__ == "__main__":
    sys.exit(main())
