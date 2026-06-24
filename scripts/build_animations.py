#!/usr/bin/env python3
"""Discover animation sidecars under ``content/`` and emit their artifacts.

An animation sidecar is a small author-written module at
``content/<collection>/<item>/animations/<name>.py`` that provides a frame source plus
declarative metadata — and imports nothing from the build:

    import numpy as np, matplotlib.pyplot as plt

    FPS = 12
    OUTPUTS = ("player", "gif")        # any of: "player", "gif", "mp4"

    def frames():                      # returns a sequence of matplotlib Figures
        ...

This hook runs during ``quarto render`` (pre-render), combines the frames with
``scripts/animation.PlotSequence``, and writes the selected artifacts to
``_generated/animations/<collection>/<item>/<name>.<ext>`` for pages to embed.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

# Resolve the sibling `animation` module whether this runs as a script (scripts/ is sys.path[0])
# or is imported as `scripts.build_animations` (e.g. from tests).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # headless render; also fixes the backend for pyplot in sidecars

from animation import PlotSequence  # noqa: E402

SITE_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = SITE_ROOT / "content"
GENERATED_ROOT = SITE_ROOT / "_generated" / "animations"
VALID_OUTPUTS = ("player", "gif", "mp4")
_EXTENSION = {"player": ".html", "gif": ".gif", "mp4": ".mp4"}


def discover_sidecars(content_root: Path = CONTENT_ROOT) -> list[Path]:
    """Return every ``content/**/animations/*.py`` sidecar, sorted."""
    if not content_root.is_dir():
        return []
    return sorted(content_root.glob("**/animations/*.py"))


def _load_module(path: Path) -> ModuleType:
    name = "anim_sidecar__" + "_".join(path.relative_to(SITE_ROOT).with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import animation sidecar: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_sequence(module: ModuleType, path: Path) -> PlotSequence:
    fps = float(getattr(module, "FPS", 8.0))
    loop = bool(getattr(module, "LOOP", False))
    if hasattr(module, "frames"):
        return PlotSequence.from_figure_list(module.frames(), fps=fps, loop=loop)
    if hasattr(module, "make_figure"):
        count = getattr(module, "FRAMES", None)
        if count is None:
            raise ValueError(f"{path}: make_figure(i) sidecars require a module-level FRAMES count")
        return PlotSequence.from_figures(module.make_figure, count, fps=fps, loop=loop)
    raise ValueError(f"{path}: sidecar must define frames() or make_figure(i)")


def output_path(sidecar: Path, output: str) -> Path:
    """Map a sidecar path + output kind to its artifact under ``_generated/animations/``."""
    # content/<collection>/<item>/animations/<name>.py -> <collection>/<item>
    item_dir = sidecar.parent.parent.relative_to(CONTENT_ROOT)
    return GENERATED_ROOT / item_dir / (sidecar.stem + _EXTENSION[output])


def build_sidecar(sidecar: Path) -> list[Path]:
    """Build every artifact a sidecar declares via ``OUTPUTS``; return the paths written."""
    module = _load_module(sidecar)
    outputs = tuple(getattr(module, "OUTPUTS", ("player",)))
    for output in outputs:
        if output not in VALID_OUTPUTS:
            raise ValueError(
                f"{sidecar}: unknown OUTPUTS entry {output!r}; choose from {VALID_OUTPUTS}"
            )
    sequence = _build_sequence(module, sidecar)
    written: list[Path] = []
    for output in outputs:
        destination = output_path(sidecar, output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if output == "player":
            destination.write_text(sequence.to_standalone_html(), encoding="utf-8")
        else:
            sequence.save(destination)
        written.append(destination)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discover-only", action="store_true", help="list sidecars without building them"
    )
    arguments = parser.parse_args()

    sidecars = discover_sidecars()
    if arguments.discover_only:
        for sidecar in sidecars:
            print(sidecar.relative_to(SITE_ROOT))
        if not sidecars:
            print("No animation sidecars discovered.")
        return

    # Rebuild from scratch so a removed or renamed sidecar leaves no orphaned artifact.
    if GENERATED_ROOT.exists():
        shutil.rmtree(GENERATED_ROOT)
    if not sidecars:
        print("No animation sidecars discovered.")
        return

    for sidecar in sidecars:
        for destination in build_sidecar(sidecar):
            print(
                f"Built {destination.relative_to(SITE_ROOT)} "
                f"from {sidecar.relative_to(SITE_ROOT)}"
            )


if __name__ == "__main__":
    main()
