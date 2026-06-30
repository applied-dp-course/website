"""Website-side tests for the shared plot inventory scanner."""

from __future__ import annotations

import importlib.util
import sys
import unittest
import warnings
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = SITE_ROOT.parent
CODE_BASE = WORKSPACE / "code_base_dev"
if str(CODE_BASE) not in sys.path:
    sys.path.insert(0, str(CODE_BASE))

from libdpy.visualization.plot_inventory import (  # noqa: E402
    FULL_PAGE_WASM_SMOKE_ROUTES,
    collect_plot_inventory_findings,
    strict_inventory_findings,
)
from libdpy.visualization.registry import embed_spec_builders  # noqa: E402


class PlotInventoryWebsiteTest(unittest.TestCase):
    def _require_monorepo_inventory(self) -> None:
        if not (CODE_BASE / "libdpy").is_dir():
            self.skipTest("shared plot inventory scanner requires the course monorepo layout")

    def test_registry_matches_build_interactives(self) -> None:
        script = SITE_ROOT / "scripts" / "build_interactives.py"
        spec = importlib.util.spec_from_file_location("build_interactives", script)
        assert spec is not None and spec.loader is not None
        build_interactives = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = build_interactives
        spec.loader.exec_module(build_interactives)

        self.assertEqual(set(embed_spec_builders()), set(build_interactives._SPEC_BUILDERS))

    def test_full_page_routes_are_documented(self) -> None:
        self.assertIn("pages/index.html", FULL_PAGE_WASM_SMOKE_ROUTES)
        self.assertIn(
            "content/lecture-presentations/privacy-auditing/presentation.html",
            FULL_PAGE_WASM_SMOKE_ROUTES,
        )

    def test_inventory_scan_strict_pre_render(self) -> None:
        self._require_monorepo_inventory()
        findings = collect_plot_inventory_findings(WORKSPACE, include_post_render=False)
        violations = strict_inventory_findings(findings, post_render=False)
        self.assertEqual(
            violations,
            [],
            msg="\n".join(str(item) for item in violations) or "plot inventory violations",
        )

    def test_inventory_scan_strict_post_render(self) -> None:
        self._require_monorepo_inventory()
        site = SITE_ROOT / "_site"
        if not site.is_dir():
            self.skipTest("website/_site not built; run quarto render first")

        findings = collect_plot_inventory_findings(WORKSPACE, include_post_render=True)
        violations = strict_inventory_findings(findings, post_render=True)
        self.assertEqual(
            violations,
            [],
            msg="\n".join(str(item) for item in violations) or "post-render plot inventory violations",
        )

    def test_inventory_scan_emits_warnings(self) -> None:
        self._require_monorepo_inventory()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            findings = collect_plot_inventory_findings(WORKSPACE)
            for finding in findings:
                warnings.warn(str(finding), UserWarning, stacklevel=1)
        self.assertIsInstance(findings, list)
        if findings:
            self.assertTrue(caught)


if __name__ == "__main__":
    unittest.main()
