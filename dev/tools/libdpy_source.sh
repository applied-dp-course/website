#!/usr/bin/env bash
# Resolve the in-tree libdpy source directory (contains pyproject.toml).
#
# Search order:
#   1. LIBDPY_SOURCE env var (explicit override)
#   2. ../code_base_dev/libdpy relative to the website repo root
#
# When sourced, defines resolve_libdpy_source. When executed, prints the path.

set -euo pipefail

_resolve_site_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

resolve_libdpy_source() {
  local site_root="${1:-$(_resolve_site_root)}"

  if [[ -n "${LIBDPY_SOURCE:-}" && -f "${LIBDPY_SOURCE}/pyproject.toml" ]]; then
    cd "${LIBDPY_SOURCE}" && pwd
    return 0
  fi

  local candidate="${site_root}/../code_base_dev/libdpy"
  if [[ -f "${candidate}/pyproject.toml" ]]; then
    cd "${candidate}" && pwd
    return 0
  fi

  return 1
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  resolve_libdpy_source || {
    echo "ERROR: could not resolve in-tree libdpy (set LIBDPY_SOURCE or clone code_base_dev beside website)" >&2
    exit 1
  }
fi
