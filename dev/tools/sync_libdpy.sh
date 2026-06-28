#!/usr/bin/env bash
# Reinstall libdpy from pub_lib `main` so the local venv matches CI.
#
# CI installs libdpy fresh from git on every run; a stale local install can pass tests
# that fail on CI (e.g. an import added on `main` that the local copy predates). Run this
# before a local render/smoke test to build the WASM wheel from the same libdpy CI uses.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIP="${PIP:-$ROOT/.venv/bin/pip}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

echo "Reinstalling libdpy from pub_lib main ..."
"$PIP" install --quiet --upgrade --force-reinstall --no-deps \
  "libdpy[notebook] @ git+https://github.com/applied-dp-course/pub_lib.git"
"$PYTHON" -c "import libdpy; print('libdpy', libdpy.__version__, '->', libdpy.__file__)"
