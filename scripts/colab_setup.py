#!/usr/bin/env python3
"""Helpers for validating Colab-safe notebook setup cells."""

from __future__ import annotations

import json
import re
from pathlib import Path

LIBDPY_GIT_INSTALL = 'libdpy @ git+https://github.com/applied-dp-course/pub_lib.git'
PIP_INSTALL_PATTERN = re.compile(
    r"""^%pip install -q "(.+)"$""",
)


def load_notebook(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def setup_cell_source(notebook: dict, *, cell_id: str = "setup") -> str:
    for cell in notebook.get("cells", []):
        if cell.get("id") == cell_id and cell.get("cell_type") == "code":
            return "".join(cell.get("source", []))
    raise ValueError(f"notebook is missing code cell {cell_id!r}")


def translate_pip_magics(source: str) -> str:
    translated_lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        match = PIP_INSTALL_PATTERN.match(stripped)
        if match:
            indent = line[: len(line) - len(stripped)]
            package = match.group(1)
            translated_lines.extend(
                [
                    f"{indent}import subprocess",
                    f"{indent}import sys",
                    (
                        f"{indent}subprocess.check_call("
                        f"[sys.executable, '-m', 'pip', 'install', '-q', {package!r}]"
                        ")"
                    ),
                ]
            )
            continue
        translated_lines.append(line)
    return "\n".join(translated_lines) + ("\n" if source.endswith("\n") else "")


def colab_setup_script(source: str) -> str:
    return translate_pip_magics(source)
