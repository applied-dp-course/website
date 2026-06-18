#!/usr/bin/env python3
"""Run a site-build script with Quarto's configured Python interpreter."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: run_site_python.py SCRIPT [ARG ...]")

    configured = os.environ.get("QUARTO_PYTHON")
    python = Path(configured).expanduser() if configured else Path(sys.executable)
    if not python.exists():
        raise SystemExit(f"configured Python interpreter does not exist: {python}")
    os.execv(str(python), [str(python), *sys.argv[1:]])


if __name__ == "__main__":
    main()
