import unittest
from pathlib import Path

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]


class AuthoringKitTest(unittest.TestCase):
    def test_documented_templates_exist(self) -> None:
        templates = SITE_ROOT / "authoring" / "templates"
        for name in ("lecture-presentation", "blog-post", "class-assignment", "offering", "tool"):
            self.assertTrue((templates / name).is_dir(), name)

    def test_main_pages_live_under_pages(self) -> None:
        for name in (
            "index.qmd",
            "schedule.qmd",
            "course.qmd",
            "lectures.qmd",
            "assignments.qmd",
            "class-assignments.qmd",
            "home-assignments.qmd",
            "tools.qmd",
            "blog.qmd",
            "syllabus.qmd",
            "archive.qmd",
            "about.qmd",
        ):
            self.assertTrue((SITE_ROOT / "pages" / name).is_file())
            self.assertFalse((SITE_ROOT / name).exists())

    def test_quarto_renders_explicit_source_collections(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        render = config["project"]["render"]
        self.assertIn("/pages/*.qmd", render)
        self.assertNotIn("/pages/offerings/*.qmd", render)
        self.assertIn("content/lecture-presentations/**/*.qmd", render)
        self.assertIn("content/blog-posts/**/*.ipynb", render)
        self.assertIn("content/class-assignments/**/*.ipynb", render)
        self.assertIn("content/home-assignments/**/*.ipynb", render)
        self.assertIn("content/tools/**/index.qmd", render)
        self.assertIn("content/site-posts/**/index.qmd", render)

    def test_authoring_guide_documents_names_and_generated_boundary(self) -> None:
        guide = (SITE_ROOT / "authoring" / "AUTHORING.md").read_text(encoding="utf-8")
        self.assertIn("Do not prefix", guide)
        self.assertIn("must never write into", guide)
        self.assertIn("_generated/apps/", guide)


if __name__ == "__main__":
    unittest.main()
