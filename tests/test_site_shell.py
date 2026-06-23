import unittest
from pathlib import Path

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]


class SiteShellTest(unittest.TestCase):
    def test_navbar_links_resolve(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        serialized = yaml.safe_dump(config["website"]["navbar"])
        self.assertIn("pages/index.qmd", serialized)
        for href in (
            "pages/index.qmd",
            "pages/schedule.qmd",
            "pages/lectures.qmd",
            "pages/assignments.qmd",
            "pages/tools.qmd",
            "pages/blog.qmd",
            "pages/syllabus.qmd",
            "pages/archive.qmd",
            "pages/about.qmd",
        ):
            self.assertTrue((SITE_ROOT / href).is_file())

    def test_home_and_syllabus_markers_remain(self) -> None:
        home = (SITE_ROOT / "pages" / "index.qmd").read_text(encoding="utf-8")
        syllabus = (SITE_ROOT / "pages" / "syllabus.qmd").read_text(encoding="utf-8")
        self.assertIn("hero-title", home)
        self.assertIn("BEGIN AUTO-GENERATED OFFERING BANNER", home)
        self.assertIn("BEGIN AUTO-GENERATED SYLLABUS LOGISTICS", syllabus)

    def test_resources_include_authored_and_generated_apps(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        resources = config["project"]["resources"]
        self.assertIn("apps/**", resources)
        self.assertIn("_generated/apps/**", resources)


if __name__ == "__main__":
    unittest.main()
