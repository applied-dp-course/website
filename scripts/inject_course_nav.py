#!/usr/bin/env python3
"""Post-render: inject Course split-nav script into every rendered HTML page."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import content_model

_MARKER = "// course-nav-split-v1"
_SCRIPT_PATH = content_model.SITE_ROOT / "theme" / "course-nav-split.js"
_STYLE_PATH = content_model.SITE_ROOT / "theme" / "course-nav-split.css"
_HEAD_CLOSE = "</head>"
_STYLE_MARKER = "course-nav-split.css"
_OLD_SCRIPT = re.compile(
    r"<script>\s*(?:// course-nav-split[^\n]*\n[\s\S]*?)</script>\s*",
    re.MULTILINE,
)
_OLD_STYLE = re.compile(
    r"<style>\s*/\* course-nav-split \*/[\s\S]*?</style>\s*",
    re.MULTILINE,
)


def upgrade_html(html: str, *, script_body: str, style_body: str) -> tuple[str, bool]:
    if "nav-menu-course" not in html and 'menu-text">Course' not in html:
        return html, False
    cleaned = _OLD_SCRIPT.sub("", html)
    cleaned = _OLD_STYLE.sub("", cleaned)
    snippet = (
        f"<style>\n/* course-nav-split */\n{style_body}\n</style>\n"
        f"<script>\n{script_body}\n</script>\n"
    )
    if _HEAD_CLOSE not in cleaned:
        return html, False
    updated = cleaned.replace(_HEAD_CLOSE, f"{snippet}{_HEAD_CLOSE}", 1)
    return updated, updated != html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=content_model.SITE_ROOT / "_site",
        help="Rendered site output directory",
    )
    args = parser.parse_args(argv)
    script_body = _SCRIPT_PATH.read_text(encoding="utf-8")
    style_body = _STYLE_PATH.read_text(encoding="utf-8")
    upgraded = 0
    for html_path in sorted(args.site_root.rglob("*.html")):
        original = html_path.read_text(encoding="utf-8")
        updated, changed = upgrade_html(original, script_body=script_body, style_body=style_body)
        if changed:
            html_path.write_text(updated, encoding="utf-8")
            upgraded += 1
    print(f"Injected course nav script into {upgraded} HTML page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
