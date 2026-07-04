#!/usr/bin/env python3
"""Compute GitHub Actions cache keys for cross-run render artifacts.

Outputs:
  key    — exact cache key (libdpy version + source fingerprint + requirements hash + marimo + scripts)
  prefix — version-scoped restore-keys prefix (libdpy version only)

The prefix prevents partial cache restores from an older libdpy tree's ``_freeze/``
after library changes (notebooks unchanged in source but affected by libdpy would otherwise
keep stale figure outputs).
"""

from __future__ import annotations

import argparse
import hashlib
import os
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


def _libdpy_source_root() -> Path:
    override = os.environ.get("LIBDPY_SOURCE")
    if override:
        path = Path(override)
        if (path / "pyproject.toml").is_file():
            return path.resolve()
        raise SystemExit(f"LIBDPY_SOURCE is not a libdpy tree: {override}")

    sibling = (SITE_ROOT.parent / "code_base_dev" / "libdpy").resolve()
    if (sibling / "pyproject.toml").is_file():
        return sibling

    raise SystemExit(
        "could not find in-tree libdpy (expected ../code_base_dev/libdpy beside website; "
        "set LIBDPY_SOURCE for overrides)"
    )


def _libdpy_version() -> str:
    init_py = _libdpy_source_root() / "__init__.py"
    text = init_py.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit(f"could not parse __version__ from {init_py}")
    return match.group(1)


def _libdpy_fingerprint() -> str:
    root = _libdpy_source_root()
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        relative = path.relative_to(root)
        hasher.update(str(relative).encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


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
        f"render-v2-libdpy-{_libdpy_version()}-src-{_libdpy_fingerprint()}"
        f"-req-{_requirements_fingerprint()}-marimo-{_marimo_version()}"
        f"-scripts-{_scripts_fingerprint()}"
    )


def cache_prefix() -> str:
    return f"render-v2-libdpy-{_libdpy_version()}-src-{_libdpy_fingerprint()}-"


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
