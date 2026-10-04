#!/usr/bin/env python3
"""Leak guard for the PUBLIC repo. Run before every push:

    python scripts/check_public.py

Fails (exit 1) if
  * a private path (CLAUDE.md, internal/, ...) is tracked or would be added, or
  * a public file mentions private business terms (partnership model, rates, fam trip, ...).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

PRIVATE_PATHS = re.compile(r"^(CLAUDE\.md|CLAUDE\.local\.md|internal/|\.env)")

# Business terms that must never appear in public files.
FORBIDDEN = [
    (re.compile(r"(?<!great )\bcommissions?\b", re.I), "commission terms"),
    (re.compile(r"\bprofit[- ]?shar", re.I), "profit-share terms"),
    (re.compile(r"\bshare partner", re.I), "partnership model"),
    (re.compile(r"\bexclusivity\b", re.I), "exclusivity terms"),
    (re.compile(r"\bfam trip", re.I), "fam trip"),
    (re.compile(r"\bQ-(MODEL|FAM)-\d+", re.I), "internal-only question id"),
    (re.compile(r"\bmark-?ups?\b", re.I), "pricing margins"),
]

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".j2", ".html", ".css", ".js", ".txt", ".json", ".svg", ""}


def candidate_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return sorted(set(out.split()))


def main() -> int:
    problems: list[str] = []
    files = candidate_files()

    for path in files:
        if PRIVATE_PATHS.match(path):
            problems.append(f"PRIVATE FILE tracked or addable: {path}")

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
