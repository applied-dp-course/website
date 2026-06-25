import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import content_model


class ContentModelTest(unittest.TestCase):
    def test_live_catalog_uses_named_collections(self) -> None:
        catalog = content_model.load_catalog()
        self.assertEqual(
            {item.name for item in catalog.lecture_presentations},
            {"reconstruction-attacks", "hypothesis-testing", "privacy-auditing"},
        )
        self.assertEqual(
            {item.name for item in catalog.blog_posts},
            {"reconstruction-attacks", "hypothesis-testing", "privacy-auditing"},
        )
        self.assertEqual(
            {item.name for item in catalog.class_assignments},
            {"hypothesis-testing"},
        )
        self.assertEqual(catalog.home_assignments, ())

    def test_offering_references_content_by_name(self) -> None:
        schedule = content_model.current_offering_schedule(content_model.load_catalog())
        self.assertEqual(schedule.rows[0].blog_post, "reconstruction-attacks")
        self.assertEqual(schedule.rows[0].lecture_presentation, "reconstruction-attacks")
        self.assertEqual(schedule.rows[1].class_assignment, "hypothesis-testing")
        self.assertEqual(schedule.rows[3].blog_post, "privacy-auditing")
        self.assertEqual(schedule.rows[3].lecture_presentation, "privacy-auditing")

    def test_numbered_content_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            item = root / "03-numbered"
            item.mkdir()
            (item / "presentation.qmd").write_text("# Deck\n", encoding="utf-8")
            (item / "manifest.yml").write_text(
                "title: Deck\nentrypoint: presentation.qmd\nstatus: draft\n",
                encoding="utf-8",
            )
            with self.assertRaises(content_model.ContentValidationError):
                content_model.discover_items(root, "lecture-presentation", ".qmd")

    def test_wrong_entrypoint_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            item = root / "topic"
            item.mkdir()
            (item / "post.qmd").write_text("# Post\n", encoding="utf-8")
            (item / "manifest.yml").write_text(
                "title: Post\nentrypoint: post.qmd\nstatus: draft\n",
                encoding="utf-8",
            )
            with self.assertRaises(content_model.ContentValidationError):
                content_model.discover_items(root, "blog-post", ".ipynb")

    def test_content_tree_has_no_generated_artifacts(self) -> None:
        content_model.validate_content_source_tree()
        forbidden = []
        for root in (
            content_model.LECTURE_PRESENTATIONS_DIR,
            content_model.BLOG_POSTS_DIR,
            content_model.CLASS_ASSIGNMENTS_DIR,
            content_model.HOME_ASSIGNMENTS_DIR,
        ):
            forbidden.extend(root.rglob("*.html"))
            forbidden.extend(root.rglob("*.quarto_ipynb"))
        self.assertEqual(forbidden, [])

    def test_content_notebooks_use_portable_python3_kernelspec(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "blog-posts" / "topic"
            root.mkdir(parents=True)
            (root / "post.ipynb").write_text(
                '{"cells":[],"metadata":{"kernelspec":{"name":"libdpy-base-local"}},"nbformat":4,"nbformat_minor":5}\n',
                encoding="utf-8",
            )
            with mock.patch.object(content_model, "BLOG_POSTS_DIR", root.parent):
                with self.assertRaises(content_model.ContentValidationError):
                    content_model.validate_content_source_tree()

    def test_content_notebooks_reject_widget_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "blog-posts" / "topic"
            root.mkdir(parents=True)
            (root / "post.ipynb").write_text(
                '{"cells":[],"metadata":{"kernelspec":{"name":"python3"},"widgets":{}},"nbformat":4,"nbformat_minor":5}\n',
                encoding="utf-8",
            )
            with mock.patch.object(content_model, "BLOG_POSTS_DIR", root.parent):
                with self.assertRaises(content_model.ContentValidationError):
                    content_model.validate_content_source_tree()


if __name__ == "__main__":
    unittest.main()
