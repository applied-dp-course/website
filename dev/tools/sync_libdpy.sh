#!/usr/bin/env bash
# Install the libdpy pin from requirements.txt (same spec CI uses).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIP="${PIP:-$ROOT/.venv/bin/pip}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

echo "Installing libdpy from pinned requirements.txt ..."
"$PIP" install --quiet --upgrade -r "$ROOT/requirements.txt"
"$PYTHON" -c "import libdpy; print('libdpy', libdpy.__version__, '->', libdpy.__file__)"
