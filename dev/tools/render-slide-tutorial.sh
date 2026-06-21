#!/usr/bin/env bash
# Render the slide-authoring sandbox (authoring/ is not part of the public site).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUARTO_BIN="${QUARTO_BIN:-$HOME/.local/quarto-1.6/bin/quarto}"
QUARTO_PYTHON="${QUARTO_PYTHON:-$ROOT/.venv/bin/python}"

export MPLBACKEND=Agg
exec "$QUARTO_BIN" render authoring/tutorials/slide-authoring/tutorial.ipynb "$@"
