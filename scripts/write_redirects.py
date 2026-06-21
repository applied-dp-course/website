#!/usr/bin/env python3
"""Write compatibility redirects from legacy ``lectures/`` URLs to ``content/lectures/``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import content_model


REDIRECT_MARKER = "<!-- legacy-lecture-redirect -->"
REDIRECT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  {marker}
  <meta http-equiv="refresh" content="0; url={target}">
  <link rel="canonical" href="{target}">
  <title>Redirecting…</title>
  <script>window.location.replace({target_json});</script>
</head>
<body>
  <p>Redirecting to <a href="{target}">{target_label}</a>.</p>
</body>
</html>
"""


def _surface_html_name(surface: str) -> str | None:
    path = Path(surface)
    if path.suffix in {".ipynb", ".qmd"}:
        return f"{path.stem}.html"
    return None


def _relative_url(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace("\\", "/")


def collect_legacy_redirects(
    catalog: content_model.ContentCatalog,
    *,
    output_root: Path,
) -> list[tuple[Path, Path]]:
    """Return ``(legacy_path, target_path)`` pairs under ``output_root``."""

    pairs: list[tuple[Path, Path]] = []
    seen: set[tuple[Path, Path]] = set()

    def add_pair(legacy: Path, target: Path) -> None:
        key = (legacy, target)
        if key in seen:
            return
        seen.add(key)
        pairs.append(key)

    for lecture in catalog.lectures:
        legacy_base = output_root / "lectures" / lecture.slug
        target_base = output_root / content_model.LECTURES_URL_PREFIX / lecture.slug

        legacy_surface_names: set[str] = set()

        for surface in (lecture.surfaces.learn, lecture.surfaces.presentation):
            html_name = _surface_html_name(surface)
            if html_name is None:
                continue
            legacy_surface_names.add(html_name)
            add_pair(legacy_base / html_name, target_base / html_name)

        # Lecture 02 still ships ``slides.qmd`` as a compatibility stub even when
        # ``notebook.ipynb`` is the declared presentation surface.
        if (
            "slides.html" not in legacy_surface_names
            and (lecture.source_path.parent / "slides.qmd").exists()
        ):
            add_pair(legacy_base / "slides.html", target_base / "slides.html")

        for app in lecture.apps:
            add_pair(
                legacy_base / app.path / "index.html",
                target_base / app.path / "index.html",
            )

    pairs.sort(key=lambda item: item[0].as_posix())
    return pairs


def _is_generated_redirect(path: Path) -> bool:
    if not path.is_file():
        return False
    return REDIRECT_MARKER in path.read_text(encoding="utf-8")


def write_redirect_page(legacy_path: Path, target_path: Path) -> None:
    relative_target = _relative_url(legacy_path, target_path)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        REDIRECT_TEMPLATE.format(
            marker=REDIRECT_MARKER,
            target=relative_target,
            target_json=repr(relative_target),
            target_label=relative_target,
        ),
        encoding="utf-8",
    )


def write_legacy_redirects(
    catalog: content_model.ContentCatalog,
    *,
    output_root: Path,
) -> list[tuple[Path, Path]]:
    written: list[tuple[Path, Path]] = []
    for legacy_path, target_path in collect_legacy_redirects(catalog, output_root=output_root):
        if not target_path.is_file():
            raise RuntimeError(
                f"redirect target missing: {target_path.relative_to(output_root)} "
                f"(needed for legacy {legacy_path.relative_to(output_root)})"
            )
        if legacy_path.is_file() and not _is_generated_redirect(legacy_path):
            raise RuntimeError(
                f"refusing to overwrite rendered page: {legacy_path.relative_to(output_root)}"
            )
        write_redirect_page(legacy_path, target_path)
        written.append((legacy_path, target_path))
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=content_model.SITE_ROOT / "_site",
        help="built site directory (default: _site/)",
    )
    args = parser.parse_args(argv)

    catalog = content_model.load_catalog()
    written = write_legacy_redirects(catalog, output_root=args.output_root)
    print(f"Wrote {len(written)} legacy lecture redirect(s).")


if __name__ == "__main__":
    main()
