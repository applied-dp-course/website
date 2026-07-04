import importlib.util
import sys
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parent / "run_smoke_tests.py"
SPEC = importlib.util.spec_from_file_location("run_smoke_tests", PATH)
run_smoke_tests = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = run_smoke_tests
SPEC.loader.exec_module(run_smoke_tests)


class SmokeTargetTest(unittest.TestCase):
    def test_dedupe_prefers_presentation_generated_path(self) -> None:
        artifact = "privacy-plot-norm-6197737a49"
        paths = run_smoke_tests.dedupe_wasm_smoke_paths(
            [
                f"_generated/apps/pages/{artifact}",
                f"_generated/apps/blog-posts/hypothesis-testing/{artifact}",
                f"_generated/apps/lecture-presentations/hypothesis-testing/{artifact}",
            ]
        )
        self.assertEqual(
            paths,
            [f"_generated/apps/lecture-presentations/hypothesis-testing/{artifact}"],
        )

    def test_live_canvas_apps_are_declared(self) -> None:
        entries = run_smoke_tests.gallery.build_gallery_entries(
            run_smoke_tests.content_model.load_catalog()
        )
        canvas = [entry for entry in entries if entry.runtime in {"external-app", "browser-native"}]
        self.assertEqual(len(canvas), 0)

    def test_built_targets_are_discoverable_when_site_exists(self) -> None:
        root = run_smoke_tests.content_model.SITE_ROOT
        output = root / "_site"
        marker = (
            output
            / "_generated"
            / "apps"
            / "lecture-presentations"
            / "hypothesis-testing"
            / "privacy-plot-norm-6197737a49"
            / "index.html"
        )
        if not marker.is_file():
            self.skipTest("_site is stale or not built for the current layout")
        try:
            wasm, canvas = run_smoke_tests.discover_smoke_targets(root, output)
        except SystemExit as exc:
            self.skipTest(f"_site is stale or incomplete: {exc}")
        self.assertEqual(len(canvas), 0)
        self.assertGreaterEqual(len(wasm), 2)

    def test_full_page_wasm_routes_are_exposed(self) -> None:
        routes = run_smoke_tests.discover_full_page_wasm_routes()
        self.assertIn("pages/index.html", routes)
        self.assertIn(
            "content/blog-posts/privacy-auditing/post.html",
            routes,
        )

    def test_filter_full_page_routes_by_slug(self) -> None:
        routes = run_smoke_tests.discover_full_page_wasm_routes()
        filtered = run_smoke_tests.filter_full_page_wasm_routes(
            routes,
            slugs=("private-estimation",),
        )
        self.assertEqual(
            filtered,
            ["content/blog-posts/private-estimation/post.html"],
        )

    def test_static_reconstruction_routes_are_skipped(self) -> None:
        routes = run_smoke_tests.discover_full_page_wasm_routes()
        self.assertNotIn(
            "content/blog-posts/reconstruction-attacks/post.html",
            routes,
        )
        self.assertNotIn(
            "content/lecture-presentations/reconstruction-attacks/presentation.html",
            routes,
        )

    def test_filter_full_page_routes_by_explicit_route(self) -> None:
        routes = run_smoke_tests.discover_full_page_wasm_routes()
        selected = ("content/blog-posts/private-estimation/post.html",)
        self.assertEqual(
            run_smoke_tests.filter_full_page_wasm_routes(routes, selected=selected),
            list(selected),
        )

    def test_shard_items_splits_deterministically(self) -> None:
        items = ["a", "b", "c", "d", "e"]
        self.assertEqual(run_smoke_tests.shard_items(items, 0, 2), ["a", "c", "e"])
        self.assertEqual(run_smoke_tests.shard_items(items, 1, 2), ["b", "d"])
        self.assertEqual(run_smoke_tests.shard_items(items, 0, 1), items)

    def test_resolve_iframe_url_normalizes_parent_segments(self) -> None:
        from smoke_full_page_wasm import _resolve_iframe_url

        page = "http://127.0.0.1:8080/content/blog-posts/privacy-auditing/post.html"
        iframe = "../../../_generated/apps/blog-posts/privacy-auditing/demo/index.html"
        self.assertEqual(
            _resolve_iframe_url(page, iframe),
            "http://127.0.0.1:8080/_generated/apps/blog-posts/privacy-auditing/demo/index.html",
        )


if __name__ == "__main__":
    unittest.main()
