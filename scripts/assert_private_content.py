#!/usr/bin/env python3
"""Fail the build if private assignment artifacts were published."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import content_model


PRIVATE_ASSIGNMENT_GLOBS = (
    "content/class-assignments/**/solution.html",
    "content/class-assignments/**/solution.ipynb",
    "content/class-assignments/**/solution_files",
    "content/home-assignments/**/solution.html",
    "content/home-assignments/**/solution.ipynb",
    "content/home-assignments/**/solution_files",
)

# Authoring kit and dev helpers must never ship on the public site.
INTERNAL_SITE_PREFIXES = (
    "authoring/",
    "dev/",
)


def find_published_solution_artifacts(site_root: Path) -> list[Path]:
    if not site_root.is_dir():
        return []

    matches: list[Path] = []
    for pattern in PRIVATE_ASSIGNMENT_GLOBS:
        matches.extend(path for path in site_root.glob(pattern) if path.exists())
    for prefix in INTERNAL_SITE_PREFIXES:
        internal_root = site_root / prefix
        if internal_root.is_dir():
            matches.extend(path for path in internal_root.rglob("*") if path.is_file())
    return sorted(set(matches), key=lambda path: path.as_posix())


def check_site(site_root: Path | None = None) -> list[Path]:
    site_root = site_root or content_model.SITE_ROOT / "_site"
    return find_published_solution_artifacts(site_root)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=content_model.SITE_ROOT / "_site",
        help="rendered site directory to inspect (default: _site/)",
    )
    args = parser.parse_args(argv)
    published = check_site(args.site_root)
    if published:
        relative_paths = [
            path.relative_to(args.site_root).as_posix() for path in published
        ]
        raise SystemExit(
            "private or internal-only artifacts were published under _site/: "
            + ", ".join(relative_paths)
        )
    print("No private or internal-only artifacts found in the rendered site.")


if __name__ == "__main__":
    main()
