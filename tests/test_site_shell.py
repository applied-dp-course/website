import unittest
from pathlib import Path

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]


class SiteShellTest(unittest.TestCase):
    def test_navbar_links_resolve(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        navbar = config["website"]["navbar"]
        serialized = yaml.safe_dump(navbar)
        self.assertIn("text: Course", serialized)
        self.assertIn("pages/syllabus.qmd", serialized)
        self.assertIn("pages/lectures.qmd", serialized)
        self.assertIn("pages/class-assignments.qmd", serialized)
        self.assertIn("pages/home-assignments.qmd", serialized)
        self.assertIn("pages/archive.qmd", serialized)
        self.assertNotIn("offerings/current", serialized)
        self.assertTrue((SITE_ROOT / "theme" / "course-nav-split.js").is_file())
        post_render = yaml.safe_dump(config["project"]["post-render"])
        self.assertIn("inject_course_nav.py", post_render)
        for href in (
            "pages/index.qmd",
            "pages/course.qmd",
            "pages/schedule.qmd",
            "pages/lectures.qmd",
            "pages/assignments.qmd",
            "pages/class-assignments.qmd",
            "pages/home-assignments.qmd",
            "pages/tools.qmd",
            "pages/blog.qmd",
            "pages/syllabus.qmd",
            "pages/archive.qmd",
            "pages/about.qmd",
        ):
            self.assertTrue((SITE_ROOT / href).is_file())

    def test_home_course_and_syllabus_markers_remain(self) -> None:
        home = (SITE_ROOT / "pages" / "index.qmd").read_text(encoding="utf-8")
        course = (SITE_ROOT / "pages" / "course.qmd").read_text(encoding="utf-8")
        syllabus = (SITE_ROOT / "pages" / "syllabus.qmd").read_text(encoding="utf-8")
        self.assertIn("hero-title", home)
        self.assertIn("BEGIN AUTO-GENERATED OFFERING BANNER", home)
        self.assertIn("BEGIN AUTO-GENERATED OFFERING BANNER", course)
        self.assertIn("BEGIN AUTO-GENERATED SYLLABUS LOGISTICS", course)
        self.assertIn("BEGIN AUTO-GENERATED SCHEDULE", syllabus)

    def test_resources_include_authored_and_generated_apps(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        resources = config["project"]["resources"]
        self.assertIn("apps/**", resources)
        self.assertIn("_generated/apps/**", resources)


if __name__ == "__main__":
    unittest.main()
