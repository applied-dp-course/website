import hashlib
import unittest
from pathlib import Path

from scripts import content_model, sync_content


SITE_ROOT = Path(__file__).resolve().parents[1]


def _content_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((SITE_ROOT / "content").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(SITE_ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


class SyncContentSiteTest(unittest.TestCase):
    def test_catalog_sync_updates_pages_not_content(self) -> None:
        before = _content_digest()
        sync_content.run_phase("catalog")
        after = _content_digest()
        self.assertEqual(before, after)
        syllabus = (SITE_ROOT / "pages" / "syllabus.qmd").read_text(encoding="utf-8")
        self.assertIn("K-anonymity", syllabus)
        self.assertIn("reconstruction-attacks/post.html", syllabus)
        self.assertIn("content/blog-posts/reconstruction-attacks/post.ipynb", syllabus)
        self.assertNotIn("| Date |", syllabus)

    def test_sync_is_idempotent(self) -> None:
        sync_content.run_phase("catalog")
        paths = [
            SITE_ROOT / "pages" / name
            for name in (
                "index.qmd",
                "course.qmd",
                "syllabus.qmd",
                "lectures.qmd",
                "class-assignments.qmd",
                "home-assignments.qmd",
                "archive.qmd",
            )
        ]
        first = {path: path.read_text(encoding="utf-8") for path in paths}
        sync_content.run_phase("catalog")
        self.assertEqual(first, {path: path.read_text(encoding="utf-8") for path in paths})

    def test_catalog_json_uses_new_collections(self) -> None:
        catalog = content_model.load_catalog()
        payload = sync_content.catalog_to_dict(catalog)
        self.assertIn("lecture_presentations", payload)
        self.assertIn("blog_posts", payload)
        self.assertIn("class_assignments", payload)
        self.assertIn("home_assignments", payload)
        self.assertNotIn("lectures", payload)

    def test_source_normalization_is_disabled(self) -> None:
        self.assertEqual(sync_content.normalize_lecture_sources(), 0)

    def test_lectures_page_follows_offering_order(self) -> None:
        rendered = sync_content.render_lectures_page(content_model.load_catalog())
        self.assertIn("Short introduction coming soon", rendered)
        self.assertIn("**Blog post**", rendered)
        self.assertIn("**Presentation**", rendered)
        self.assertIn("K-anonymity", rendered)
        self.assertLess(rendered.index("K-anonymity"), rendered.index("Reconstruction Attacks"))
        self.assertLess(rendered.index("Reconstruction Attacks"), rendered.index("Privacy Auditing"))

    def test_syllabus_table_omits_dates(self) -> None:
        rendered = sync_content.render_syllabus_page(content_model.load_catalog())
        self.assertIn("| Week | Topic |", rendered)
        self.assertNotIn("| Date |", rendered)


if __name__ == "__main__":
    unittest.main()
