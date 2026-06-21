import unittest
from pathlib import Path

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]


class SiteShellTest(unittest.TestCase):
    def test_blog_listing_targets_example_post(self) -> None:
        blog_index = SITE_ROOT / "blog" / "index.qmd"
        self.assertTrue(blog_index.is_file())
        front_matter = yaml.safe_load(blog_index.read_text(encoding="utf-8").split("---", 2)[1])
        self.assertEqual(front_matter["listing"]["contents"], "posts")

        post_path = SITE_ROOT / "blog" / "posts" / "gaussian-privacy-tradeoff" / "index.qmd"
        self.assertTrue(post_path.is_file())
        post_meta = yaml.safe_load(post_path.read_text(encoding="utf-8").split("---", 2)[1])
        self.assertIn("date", post_meta)
        self.assertIn("description", post_meta)
        self.assertTrue(post_meta.get("categories"))

    def test_navbar_links_resolve_to_site_pages(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        navbar = config["website"]["navbar"]
        hrefs: list[str] = []
        for item in navbar["left"]:
            if isinstance(item, dict) and "href" in item:
                hrefs.append(item["href"])
        for item in navbar["right"]:
            if isinstance(item, dict) and "menu" in item:
                for entry in item["menu"]:
                    if isinstance(entry, dict) and "href" in entry:
                        hrefs.append(entry["href"])

        for href in hrefs:
            self.assertTrue(
                (SITE_ROOT / href).is_file(),
                f"navbar href {href!r} does not resolve to a source file",
            )

    def test_navbar_excludes_internal_planning_pages(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        navbar = config["website"]["navbar"]
        serialized = yaml.dump(navbar)
        for forbidden in ("WEBSITE_PLAN", "STATUS.md", "PLAN.md", "tutorials/"):
            self.assertNotIn(forbidden, serialized)

    def test_quarto_resources_include_blog_and_home_apps(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        resources = config["project"]["resources"]
        self.assertIn("blog/**/apps/**", resources)
        self.assertIn("apps/**", resources)

    def test_theme_and_about_page_exist(self) -> None:
        self.assertTrue((SITE_ROOT / "theme" / "custom.scss").is_file())
        self.assertTrue((SITE_ROOT / "about.qmd").is_file())

    def test_home_page_hides_default_title_block(self) -> None:
        front_matter = yaml.safe_load(
            (SITE_ROOT / "index.qmd").read_text(encoding="utf-8").split("---", 2)[1]
        )
        self.assertEqual(front_matter.get("title-block-style"), "none")
        body = (SITE_ROOT / "index.qmd").read_text(encoding="utf-8").split("---", 2)[2]
        self.assertIn("hero-title", body)
        self.assertNotIn("{.unlisted", body)

    def test_syllabus_has_logistics_marker(self) -> None:
        syllabus = (SITE_ROOT / "syllabus.qmd").read_text(encoding="utf-8")
        self.assertIn("BEGIN AUTO-GENERATED SYLLABUS LOGISTICS", syllabus)
        self.assertIn("END AUTO-GENERATED SYLLABUS LOGISTICS", syllabus)


if __name__ == "__main__":
    unittest.main()
