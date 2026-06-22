#!/usr/bin/env bash
# Full site render — same recipe as CI (see README.md "Build & preview locally").
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUARTO_BIN="${QUARTO_BIN:-$HOME/.local/quarto-1.6/bin/quarto}"
QUARTO_PYTHON="${QUARTO_PYTHON:-$ROOT/.venv/bin/python}"

export MPLBACKEND=Agg
exec "$QUARTO_BIN" render --execute "$@"
