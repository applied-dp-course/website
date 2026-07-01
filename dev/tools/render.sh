#!/usr/bin/env bash
# Full site render — same recipe as CI (see README.md "Build & preview locally").
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUARTO_BIN="${QUARTO_BIN:-$HOME/.local/quarto-1.6/bin/quarto}"
QUARTO_PYTHON="${QUARTO_PYTHON:-$ROOT/.venv/bin/python}"
export QUARTO_PYTHON

# Ensure the venv satisfies the libdpy pin in requirements.txt before the pre-render hook
# builds the WASM wheel. Set LIBDPY_SYNC=0 to skip (offline / already satisfied).
if [ "${LIBDPY_SYNC:-1}" != "0" ]; then
  "$(dirname "$0")/sync_libdpy.sh"
fi

export MPLBACKEND=Agg
exec "$QUARTO_BIN" render --execute "$@"
