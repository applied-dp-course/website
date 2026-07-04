#!/usr/bin/env bash
# Install host deps and the in-tree libdpy editable (sibling code_base_dev/libdpy).
#
# Dev/CI site builds import libdpy from the library next to the site — not from pub_lib.
# Student pip installs still use pub_lib tags (see requirements-pub-lib-pin.txt).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=libdpy_source.sh
source "$(dirname "$0")/libdpy_source.sh"

PIP="${PIP:-$ROOT/.venv/bin/pip}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

LIBDPY_SRC="$(resolve_libdpy_source "$ROOT")" || {
  echo "ERROR: sibling code_base_dev/libdpy not found (expected ${ROOT}/../code_base_dev/libdpy)" >&2
  echo "  Set LIBDPY_SOURCE to the libdpy directory, or clone code_base_dev beside website." >&2
  exit 1
}

echo "Installing host dependencies from requirements.txt ..."
"$PIP" install --quiet --upgrade -r "$ROOT/requirements.txt"

echo "Installing libdpy editable from ${LIBDPY_SRC} ..."
"$PIP" install --quiet --upgrade -e "${LIBDPY_SRC}[notebook]"

"$PYTHON" -c "
import libdpy
from pathlib import Path
src = Path('${LIBDPY_SRC}').resolve()
installed = Path(libdpy.__file__).resolve()
# Editable installs resolve through .venv site-packages; confirm the package tree matches.
if installed.parent.name == 'libdpy' and not str(installed).startswith(str(src)):
    # Normal editable: __file__ may be under site-packages with .pth link — still OK if import works.
    pass
print('libdpy', libdpy.__version__, '->', libdpy.__file__)
"
