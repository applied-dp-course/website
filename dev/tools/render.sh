#!/usr/bin/env bash
# Full site render — same recipe as CI (see README.md "Build & preview locally").
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUARTO_BIN="${QUARTO_BIN:-$HOME/.local/quarto-1.6/bin/quarto}"
QUARTO_PYTHON="${QUARTO_PYTHON:-$ROOT/.venv/bin/python}"

# Align the local libdpy with CI (fresh from pub_lib main) before the pre-render hook
# builds the WASM wheel from it. Set LIBDPY_SYNC=0 to skip (offline / intentional pin).
if [ "${LIBDPY_SYNC:-1}" != "0" ]; then
  "$(dirname "$0")/sync_libdpy.sh"
fi

export MPLBACKEND=Agg
exec "$QUARTO_BIN" render --execute "$@"
