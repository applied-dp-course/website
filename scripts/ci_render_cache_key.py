#!/usr/bin/env python3
"""Compute GitHub Actions cache keys for cross-run render artifacts.

Outputs:
  key    — exact cache key (libdpy pin + requirements.txt hash + marimo + build scripts)
  prefix — version-scoped restore-keys prefix (libdpy pin only)

The prefix prevents partial cache restores from an older libdpy pin's ``_freeze/``
after a bump (notebooks unchanged in source but affected by libdpy would otherwise
keep stale figure outputs).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = SITE_ROOT / "requirements.txt"

SCRIPT_PATHS = (
    "scripts/build_interactives.py",
    "scripts/build_animations.py",
    "scripts/content_model.py",
    "scripts/sync_content.py",
    "_quarto.yml",
)


def _libdpy_pin() -> str:
    text = REQUIREMENTS.read_text(encoding="utf-8")
    match = re.search(r"pub_lib\.git@(\S+)", text)
    if not match:
        raise SystemExit("could not parse libdpy pin from requirements.txt")
    return match.group(1)


def _marimo_version() -> str:
    text = REQUIREMENTS.read_text(encoding="utf-8")
    match = re.search(r"^marimo==(\S+)", text, re.MULTILINE)
    return match.group(1) if match else "unknown"


def _requirements_fingerprint() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()[:12]


def _scripts_fingerprint() -> str:
    hasher = hashlib.sha256()
    for relative in SCRIPT_PATHS:
        path = SITE_ROOT / relative
        if not path.is_file():
            raise SystemExit(f"render cache input missing: {relative}")
        hasher.update(relative.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


def cache_key() -> str:
    return (
        f"render-v1-libdpy-{_libdpy_pin()}-req-{_requirements_fingerprint()}"
        f"-marimo-{_marimo_version()}-scripts-{_scripts_fingerprint()}"
    )


def cache_prefix() -> str:
    return f"render-v1-libdpy-{_libdpy_pin()}-"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        choices=("key", "prefix"),
        default="key",
        help="which value to print (default: key)",
    )
    arguments = parser.parse_args()
    if arguments.output == "prefix":
        print(cache_prefix())
    else:
        print(cache_key())


if __name__ == "__main__":
    main()
