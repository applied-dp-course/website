import tempfile
import unittest
from pathlib import Path

from scripts import check_site, content_model


class CheckSiteTest(unittest.TestCase):
    def test_internal_target_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            page = root / "pages" / "schedule.html"
            page.parent.mkdir()
            page.write_text("", encoding="utf-8")
            target = check_site.resolve_internal_target(root, page, "../content/topic.html")
            self.assertEqual(target, (root / "content" / "topic.html").resolve())

    def test_broken_internal_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            page = root / "index.html"
            page.write_text('<a href="missing.html">bad</a>', encoding="utf-8")
            errors = check_site.check_internal_links(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("missing.html", errors[0])

    def test_required_routes_include_pages_and_named_content(self) -> None:
        routes = check_site.required_routes(content_model.load_catalog())
        self.assertIn("pages/index.html", routes)
        self.assertIn("content/blog-posts/privacy-auditing/post.html", routes)
        self.assertIn("pages/blog.html", routes)
        self.assertIn(
            "content/lecture-presentations/hypothesis-testing/presentation.html",
            routes,
        )

    def test_built_site_passes_when_present(self) -> None:
        site = content_model.SITE_ROOT / "_site"
        if not (
            site / "_generated" / "apps" / "lecture-presentations" / "hypothesis-testing"
        ).is_dir():
            self.skipTest("_site is stale or not built for the current layout")
        self.assertEqual(check_site.check_local_site(site), [])


if __name__ == "__main__":
    unittest.main()
