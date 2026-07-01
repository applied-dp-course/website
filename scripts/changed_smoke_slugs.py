#!/usr/bin/env python3
"""Derive lecture/content slugs whose smoke tests should run for a git diff."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

# content/<collection>/<slug>/... or _generated/apps/<collection>/<slug>/...
_SLUG_PATTERNS = (
    re.compile(r"^content/[^/]+/([^/]+)/"),
    re.compile(r"^_generated/apps/[^/]+/([^/]+)/"),
    re.compile(r"^pages/index\.qmd$"),
)


def _git_diff_names(base_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def slugs_from_paths(paths: list[str]) -> list[str]:
    """Return sorted unique slugs implied by changed paths."""

    slugs: set[str] = set()
    for path in paths:
        normalized = PurePosixPath(path).as_posix()
        for pattern in _SLUG_PATTERNS:
            match = pattern.match(normalized)
            if not match:
                continue
            slug = match.group(1) if match.lastindex else "home"
            slugs.add(slug)
            break
    return sorted(slugs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "base_ref",
        nargs="?",
        default="origin/main",
        help="Git ref to diff against (default: origin/main)",
    )
    arguments = parser.parse_args()
    try:
        paths = _git_diff_names(arguments.base_ref)
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr or str(error)) from error
    for slug in slugs_from_paths(paths):
        print(slug)


if __name__ == "__main__":
    main()
