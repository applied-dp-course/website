import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SITE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import defer_wasm_embeds


SAMPLE_EMBED = (
    '<div class="libdpy-interactive" data-libdpy-interactive="privacy_plot" '
    'style="position:relative;min-height:750px;">'
    '<iframe src="apps/privacy-plot-norm-6197737a49/index.html" width="100%" '
    'height="750" loading="lazy" title="Privacy bound explorer" '
    'data-libdpy-interactive="privacy_plot" style="border:0;width:100%;display:block;" '
    'onload="hideLater()"></iframe>'
    '<div class="libdpy-interactive-loading" style="position:absolute;inset:0;'
    'display:flex;background:#fafafa;"></div>'
    "</div>"
)

SAMPLE_ANIMATION_IFRAME = (
    '<iframe src="../../../_generated/animations/blog-posts/privacy-auditing/'
    'fixed-threshold-audit-same-sample.html" width="100%" height="430" style="border:0">'
    "</iframe>"
)


class DeferWasmEmbedsTest(unittest.TestCase):
    def test_upgrade_removes_eager_iframe_src(self) -> None:
        updated, count = defer_wasm_embeds.upgrade_embed_html(SAMPLE_EMBED)
        self.assertEqual(count, 1)
        self.assertNotRegex(updated, r'<iframe\b[^>]*\ssrc="')
        self.assertIn('data-libdpy-src="apps/privacy-plot-norm-6197737a49/index.html"', updated)
        self.assertNotIn("data-libdpy-data-libdpy-src", updated)
        self.assertNotIn("libdpy-interactive-gate", updated)
        self.assertIn("display:flex", updated)

    def test_upgrade_is_idempotent(self) -> None:
        once, count = defer_wasm_embeds.upgrade_embed_html(SAMPLE_EMBED)
        self.assertEqual(count, 1)
        twice, again = defer_wasm_embeds.upgrade_embed_html(once)
        self.assertEqual(again, 0)
        self.assertEqual(twice, once)
        self.assertNotIn("data-libdpy-data-libdpy-src", twice)

    def test_animation_iframe_is_not_eager_wasm_iframe(self) -> None:
        html = f"<html><body>{SAMPLE_ANIMATION_IFRAME}</body></html>"
        self.assertFalse(defer_wasm_embeds.has_eager_wasm_iframe_src(html))

    def test_process_site_repairs_doubled_defer_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            page = site_root / "pages" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                '<html><body><div class="libdpy-interactive">'
                '<iframe data-libdpy-data-libdpy-src="apps/demo/index.html"></iframe>'
                "</div></body></html>",
                encoding="utf-8",
            )
            defer_wasm_embeds.process_site(site_root)
            rendered = page.read_text(encoding="utf-8")
            self.assertIn("data-libdpy-src=", rendered)
            self.assertNotIn("data-libdpy-data-libdpy-src", rendered)

    def test_process_site_upgrades_rendered_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            page = site_root / "tools" / "demo" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                "\n".join(
                    [
                        "<html><body>",
                        SAMPLE_EMBED,
                        "</body></html>",
                    ]
                ),
                encoding="utf-8",
            )
            count = defer_wasm_embeds.process_site(site_root)
            self.assertEqual(count, 1)
            rendered = page.read_text(encoding="utf-8")
            self.assertNotRegex(rendered, r'<iframe\b[^>]*\ssrc="')
            self.assertIn('id="libdpy-auto-load"', rendered)
            self.assertIn("DOMContentLoaded", rendered)
            self.assertNotIn("libdpy-interactive-gate", rendered)


class LiveRepositoryDeferredEmbedsTest(unittest.TestCase):
    def test_built_site_has_no_eager_wasm_iframe_src(self) -> None:
        site_root = SITE_ROOT / "_site"
        if not site_root.is_dir():
            self.skipTest("_site not built")
        defer_wasm_embeds.process_site(site_root)
        offenders: list[str] = []
        for path in site_root.rglob("*.html"):
            html = path.read_text(encoding="utf-8")
            if 'class="libdpy-interactive"' not in html:
                continue
            if defer_wasm_embeds.has_eager_wasm_iframe_src(html):
                offenders.append(path.relative_to(site_root).as_posix())
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
