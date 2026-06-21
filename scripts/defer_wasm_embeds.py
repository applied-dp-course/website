#!/usr/bin/env python3
"""Post-render upgrade: defer WASM iframe loads until after the page is ready."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import content_model

_LOADING_WATCH = (
    "(function(f){"
    "var ov=f.parentNode.querySelector('.libdpy-interactive-loading');"
    "if(!ov){return;}"
    "var hide=function(){ov.style.display='none';};"
    "var ready=function(){"
    "var doc;try{doc=f.contentDocument;}catch(e){return true;}"
    "if(!doc){return false;}var found=false;"
    "(function walk(r){"
    "if(r.shadowRoot){walk(r.shadowRoot);}"
    "r.querySelectorAll('*').forEach(function(e){"
    "if(e.tagName&&e.tagName.toLowerCase()==='marimo-slider'){found=true;}"
    "if(e.shadowRoot){walk(e.shadowRoot);}});"
    "})(doc);return found;};"
    "var t=setInterval(function(){if(ready()){clearInterval(t);hide();}},400);"
    "setTimeout(function(){clearInterval(t);hide();},60000);"
    "})(this)"
)

_EMBED_BLOCK = re.compile(
    r'(<div class="libdpy-interactive"[^>]*>)'
    r'(<iframe\b[^>]*\bsrc="([^"]+)"[^>]*></iframe>)'
    r'(<div class="libdpy-interactive-loading"[^>]*style=")([^"]*)(")',
    re.DOTALL,
)


def upgrade_embed_html(html: str) -> tuple[str, int]:
    """Remove eager iframe ``src`` attributes; load after ``DOMContentLoaded``."""

    upgraded = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal upgraded
        upgraded += 1
        opening_div = match.group(1)
        iframe_tag = match.group(2)
        src = match.group(3)
        loading_prefix = match.group(4)
        loading_style = match.group(5)
        loading_suffix = match.group(6)

        iframe_tag = re.sub(r'\sloading="lazy"', "", iframe_tag)
        iframe_tag = iframe_tag.replace(f'src="{src}"', f'data-libdpy-src="{src}"')
        if "onload=" not in iframe_tag:
            iframe_tag = iframe_tag.replace(
                "></iframe>",
                f' onload="{_LOADING_WATCH}"></iframe>',
            )

        return (
            f"{opening_div}{iframe_tag}"
            f"{loading_prefix}{loading_style}{loading_suffix}"
        )

    return _EMBED_BLOCK.sub(_replace, html), upgraded


_EAGER_IFRAME_SRC = re.compile(r'<iframe\b[^>]*\ssrc="')


def has_eager_wasm_iframe_src(html: str) -> bool:
    return _EAGER_IFRAME_SRC.search(html) is not None


_AUTO_LOAD_SCRIPT = """\
(function () {
  function activate(container) {
    var iframe = container.querySelector("iframe[data-libdpy-src]");
    if (!iframe || iframe.getAttribute("src")) {
      return;
    }
    var loading = container.querySelector(".libdpy-interactive-loading");
    if (loading) {
      loading.style.display = "flex";
    }
    iframe.setAttribute("src", iframe.getAttribute("data-libdpy-src"));
  }

  function scan() {
    document.querySelectorAll(".libdpy-interactive").forEach(activate);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan);
  } else {
    scan();
  }
})();
"""


def _ensure_auto_load_handler(html: str) -> str:
    marker = 'id="libdpy-auto-load"'
    if marker in html:
        return html
    script = (
        f'<script {marker} type="application/javascript">\n'
        f"{_AUTO_LOAD_SCRIPT}\n"
        "</script>"
    )
    if "</body>" in html:
        return html.replace("</body>", f"{script}\n</body>", 1)
    return html + script


def _strip_legacy_click_gate(html: str) -> str:
    """Remove click-to-load overlays from pages built before auto-load."""
    return re.sub(
        r'<div class="libdpy-interactive-gate"[^>]*>.*?</div>\s*',
        "",
        html,
        flags=re.DOTALL,
    )


def _strip_legacy_click_script(html: str) -> str:
    return re.sub(
        r'<script id="libdpy-click-to-load"[^>]*>.*?</script>\s*',
        "",
        html,
        flags=re.DOTALL,
    )


def process_site(site_root: Path) -> int:
    if not site_root.is_dir():
        raise SystemExit(f"site output directory not found: {site_root}")

    pages_upgraded = 0
    embeds_upgraded = 0
    for path in sorted(site_root.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        cleaned = _strip_legacy_click_script(_strip_legacy_click_gate(original))
        updated, count = upgrade_embed_html(cleaned)
        if 'data-libdpy-src="' in updated:
            updated = _ensure_auto_load_handler(updated)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        pages_upgraded += 1
        embeds_upgraded += count
    return embeds_upgraded if pages_upgraded else 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=content_model.SITE_ROOT / "_site",
        help="rendered site directory (default: _site/)",
    )
    args = parser.parse_args(argv)
    count = process_site(args.site_root)
    print(f"Deferred {count} WASM embed(s) to post-DOMContentLoaded auto-load.")


if __name__ == "__main__":
    main()
