#!/usr/bin/env python3
"""Build the Ephesian Tours site.

    python build.py            # validate content/*.yaml and render dist/
    python build.py --strict   # also fail on warnings (e.g. pending items with preview_mode off)

Steps: load YAML -> validate with the pydantic models in models.py -> render
templates/base.html.j2 with Jinja2 -> copy assets/ -> write dist/.nojekyll.
Any schema error stops the build with a non-zero exit code.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from pydantic import BaseModel, ValidationError

import models

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"

# content file stem -> model that validates it
CONTENT_MODELS: dict[str, type[BaseModel]] = {
    "site": models.Site,
}


class BuildError(Exception):
    pass


def load_yaml(path: Path) -> object:
    if not path.exists():
        raise BuildError(f"missing content file: {path.relative_to(ROOT)}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BuildError(f"{path.relative_to(ROOT)}: invalid YAML\n{exc}") from exc


def load_content() -> dict[str, BaseModel]:
    content: dict[str, BaseModel] = {}
    errors: list[str] = []
    for stem, model in CONTENT_MODELS.items():
        path = CONTENT / f"{stem}.yaml"
        try:
            content[stem] = model.model_validate(load_yaml(path))
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or "(root)"
                errors.append(f"content/{stem}.yaml: {loc}: {err['msg']}")
        except BuildError as exc:
            errors.append(str(exc))
    if errors:
        raise BuildError("content validation failed:\n  " + "\n  ".join(errors))
    return content


def render(content: dict[str, BaseModel]) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("base.html.j2").render(**content)


def write_dist(html: str) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(html, encoding="utf-8")
    (DIST / ".nojekyll").touch()  # serve files as-is on GitHub Pages
    if ASSETS.exists():
        shutil.copytree(ASSETS, DIST / "assets", ignore=shutil.ignore_patterns(".DS_Store"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    warnings: list[str] = []
    try:
        content = load_content()
        write_dist(render(content))
    except BuildError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if warnings and args.strict:
        print("BUILD FAILED: warnings with --strict", file=sys.stderr)
        return 1

    print(f"built {(DIST / 'index.html').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
