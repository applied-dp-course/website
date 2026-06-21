#!/usr/bin/env bash
# Preview the rendered site locally (run ./dev/tools/render.sh first).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUARTO_BIN="${QUARTO_BIN:-$HOME/.local/quarto-1.6/bin/quarto}"
exec "$QUARTO_BIN" preview _site "$@"
