#!/usr/bin/env python3
"""Verify every ``libdpy`` symbol imported by website content resolves on the installed package.

This is the cheap API-drift tripwire. The website deck (`presentation.qmd`) and blog
post (`post.ipynb`) are hand-kept copies of the private dev notebook; when `libdpy`
helpers are renamed or removed they silently import dead symbols, and the only place
that surfaces today is a ~7-minute Quarto render (locally) or a cryptic "Render site"
failure on CI *after* the commit is already pushed. This script parses the libdpy
imports out of content sources and resolves each one against the **installed** package
(the in-tree sibling install from ``sync_libdpy.sh``), so drift fails in seconds,
before any render.

Run it with the site venv so it sees the installed package:

    ./.venv/bin/python dev/tools/verify_libdpy_imports.py                 # all content
    ./.venv/bin/python dev/tools/verify_libdpy_imports.py --slug private-subgroup-comparisons
    ./.venv/bin/python dev/tools/verify_libdpy_imports.py --sync          # sync libdpy first

Exit status:
    0  every imported libdpy name resolves
    1  one or more names are missing (details printed)
    2  usage / environment error (e.g. --slug matched no content)
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = SITE_ROOT / "content"
PAGES_ROOT = SITE_ROOT / "pages"
SYNC_SCRIPT = SITE_ROOT / "dev" / "tools" / "sync_libdpy.sh"

# Same ```{python} / ```python code-fence shape scripts/build_interactives.py discovers.
_PYTHON_FENCE = re.compile(
    r"^```(?:\{python\}|python)\s*$\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
# Private solution notebooks are excluded from the rendered site (see _quarto.yml); they
# may import instructor-only modules that never ship to pub_lib, so skip them here too.
_SKIP_NAMES = {"solution.ipynb"}


@dataclass(frozen=True)
class ImportRef:
    source: Path
    module: str  # e.g. "libdpy.visualization.roc_plots" or "libdpy"
    name: str | None  # imported name, or None for `import libdpy.x` / `from ... import *`


def _installed_libdpy_label() -> str:
    try:
        import libdpy
    except Exception:  # noqa: BLE001
        return "<libdpy not installed>"
    return f"v{libdpy.__version__} ({libdpy.__file__})"


def _python_blocks(path: Path) -> list[str]:
    if path.suffix == ".qmd":
        return _PYTHON_FENCE.findall(path.read_text(encoding="utf-8"))
    if path.suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        return [
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        ]
    return []


def _content_roots(slugs: tuple[str, ...]) -> tuple[list[Path], list[str]]:
    """Return (roots to scan, slugs that matched nothing)."""

    if not slugs:
        return [CONTENT_ROOT, PAGES_ROOT], []
    roots: list[Path] = []
    missing: list[str] = []
    for slug in slugs:
        matches = [path for path in CONTENT_ROOT.glob(f"*/{slug}") if path.is_dir()]
        if matches:
            roots.extend(matches)
        else:
            missing.append(slug)
    return roots, missing


def _content_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for pattern in ("*.qmd", "*.ipynb"):
            for path in root.rglob(pattern):
                if path.name in _SKIP_NAMES:
                    continue
                files.add(path)
    return sorted(files)


def extract_libdpy_imports(path: Path) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for block in _python_blocks(path):
        try:
            tree = ast.parse(block)
        except SyntaxError:
            # IPython magics / shell escapes are valid lecture code but not Python AST.
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module != "libdpy" and not module.startswith("libdpy."):
                    continue
                for alias in node.names:
                    refs.append(ImportRef(path, module, None if alias.name == "*" else alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "libdpy" or alias.name.startswith("libdpy."):
                        refs.append(ImportRef(path, alias.name, None))
    return refs


def resolve_failure(ref: ImportRef) -> str | None:
    """Return an error string if the reference does not resolve, else ``None``."""

    try:
        module = importlib.import_module(ref.module)
    except Exception as error:  # noqa: BLE001 - report any import-time failure
        return f"cannot import module '{ref.module}' ({error.__class__.__name__}: {error})"
    if ref.name is None:
        return None
    if hasattr(module, ref.name):
        return None
    # `from libdpy.pkg import submodule` — attribute may only exist once imported.
    try:
        importlib.import_module(f"{ref.module}.{ref.name}")
    except Exception:  # noqa: BLE001
        return f"'{ref.module}' has no attribute or submodule '{ref.name}'"
    return None


def _run_sync() -> None:
    if not SYNC_SCRIPT.is_file():
        raise SystemExit(f"sync script not found: {SYNC_SCRIPT}")
    print(f"Syncing in-tree libdpy via {SYNC_SCRIPT.name} ...", flush=True)
    subprocess.run(["bash", str(SYNC_SCRIPT)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        metavar="SLUG",
        help="Only scan this content slug (repeatable). Default: all content + pages.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run dev/tools/sync_libdpy.sh (install sibling libdpy) before checking.",
    )
    args = parser.parse_args(argv)

    if args.sync:
        _run_sync()

    roots, missing_slugs = _content_roots(tuple(args.slug))
    if missing_slugs:
        # Fail closed: a mistyped slug must not silently pass as "nothing to check".
        print(
            f"ERROR: no content directory found for slug(s): {', '.join(missing_slugs)}",
            file=sys.stderr,
        )
        return 2

    files = _content_files(roots)
    refs: list[ImportRef] = []
    for path in files:
        refs.extend(extract_libdpy_imports(path))

    label = _installed_libdpy_label()
    scope = ", ".join(args.slug) if args.slug else "all content + pages"
    print(f"Verifying {len(refs)} libdpy import(s) across {len(files)} file(s) [{scope}] against {label}")

    failures: list[tuple[ImportRef, str]] = []
    for ref in refs:
        error = resolve_failure(ref)
        if error is not None:
            failures.append((ref, error))

    if not failures:
        print("OK: every libdpy symbol imported by content resolves on the installed package.")
        return 0

    print(
        f"\nFAILED: {len(failures)} unresolved libdpy import(s) — content is ahead of installed libdpy:\n",
        file=sys.stderr,
    )
    by_file: dict[Path, list[tuple[ImportRef, str]]] = {}
    for ref, error in failures:
        by_file.setdefault(ref.source, []).append((ref, error))
    for source in sorted(by_file):
        print(f"  {source.relative_to(SITE_ROOT)}", file=sys.stderr)
        for ref, error in by_file[source]:
            target = ref.module if ref.name is None else f"{ref.module}.{ref.name}"
            print(f"    - {target}: {error}", file=sys.stderr)
    print(
        "\nFix: implement the missing symbols in code_base_dev/libdpy/, run "
        "./dev/tools/sync_libdpy.sh, and align the content imports.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
