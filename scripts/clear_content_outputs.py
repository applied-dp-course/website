#!/usr/bin/env python3
"""Remove execution outputs that Quarto writes back into authored notebooks."""

from __future__ import annotations

import json
from pathlib import Path

import content_model


def clear_notebook(path: Path) -> bool:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("outputs"):
            cell["outputs"] = []
            changed = True
        if cell.get("execution_count") is not None:
            cell["execution_count"] = None
            changed = True
    metadata = notebook.get("metadata", {})
    if isinstance(metadata, dict) and metadata.pop("widgets", None) is not None:
        notebook["metadata"] = metadata
        changed = True
    if changed:
        path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    cleared = 0
    for directory in (
        content_model.BLOG_POSTS_DIR,
        content_model.CLASS_ASSIGNMENTS_DIR,
        content_model.HOME_ASSIGNMENTS_DIR,
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.ipynb")):
            cleared += int(clear_notebook(path))
    print(f"Cleared generated outputs from {cleared} content notebook(s).")


if __name__ == "__main__":
    main()
