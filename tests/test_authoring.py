"""Tests for the authoring kit and dev/ layout (Phase 7)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SITE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SITE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import content_model
TEMPLATES = SITE_ROOT / "authoring" / "templates"


class AuthoringKitTest(unittest.TestCase):
    def test_authoring_guide_and_templates_exist(self) -> None:
        self.assertTrue((SITE_ROOT / "authoring" / "AUTHORING.md").is_file())
        for name in ("lecture", "assignment", "tool", "blog", "offering"):
            self.assertTrue((TEMPLATES / name).is_dir(), f"missing template {name}")

    def test_plan_docs_live_under_dev_plan(self) -> None:
        plan_dir = SITE_ROOT / "dev" / "plan"
        self.assertTrue((plan_dir / "WEBSITE_PLAN.md").is_file())
        self.assertTrue((plan_dir / "WEBSITE_IMPLEMENTATION_PLAN.md").is_file())
        self.assertFalse((SITE_ROOT / "WEBSITE_PLAN.md").exists())

    def test_slide_authoring_tutorial_moved(self) -> None:
        tutorial = SITE_ROOT / "authoring" / "tutorials" / "slide-authoring" / "tutorial.ipynb"
        self.assertTrue(tutorial.is_file())
        self.assertFalse((SITE_ROOT / "tutorials").exists())

    def test_dev_tools_render_script_exists(self) -> None:
        render_script = SITE_ROOT / "dev" / "tools" / "render.sh"
        self.assertTrue(render_script.is_file())
        self.assertTrue(render_script.stat().st_mode & 0o111)

    def test_quarto_render_excludes_authoring_and_dev(self) -> None:
        config = yaml.safe_load((SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8"))
        render_globs = config["project"]["render"]
        serialized = yaml.dump(render_globs)
        self.assertNotIn("authoring/", serialized)
        self.assertNotIn("dev/", serialized)

    def test_template_lecture_passes_validation_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lectures_dir = Path(tmp) / "lectures"
            assignments_dir = Path(tmp) / "assignments"
            offerings_dir = Path(tmp) / "offerings"
            shutil.copytree(TEMPLATES / "lecture", lectures_dir / "04-mechanisms")
            shutil.copytree(TEMPLATES / "assignment", assignments_dir / "mechanisms-hw")
            shutil.copytree(TEMPLATES / "offering", offerings_dir / "2027-spring")

            # Wire schedule to copied catalog slugs.
            schedule = offerings_dir / "2027-spring" / "schedule.csv"
            schedule.write_text(
                "week,date,topic,lecture,presentation,assignment,notes\n"
                "1,2027-01-19,Mechanisms,04-mechanisms,04-mechanisms,mechanisms-hw,\n",
                encoding="utf-8",
            )

            course_dir = Path(tmp)
            (course_dir / "course.yml").write_text(
                "title: Test Course\n"
                "repo:\n  owner: owner\n  name: repo\n  branch: main\n"
                "current_offering: 2027-spring\n"
                "instructors: []\n"
                "colab:\n  enabled: false\n",
                encoding="utf-8",
            )

            original_content = content_model.CONTENT_DIR
            try:
                content_model.CONTENT_DIR = Path(tmp)
                content_model.LECTURES_DIR = lectures_dir
                content_model.ASSIGNMENTS_DIR = assignments_dir
                content_model.OFFERINGS_DIR = offerings_dir
                catalog = content_model.load_catalog(
                    lectures_dir=lectures_dir,
                    assignments_dir=assignments_dir,
                )
            finally:
                content_model.CONTENT_DIR = original_content
                content_model.LECTURES_DIR = original_content / "lectures"
                content_model.ASSIGNMENTS_DIR = original_content / "assignments"
                content_model.OFFERINGS_DIR = original_content / "offerings"

            self.assertEqual(len(catalog.lectures), 1)
            self.assertEqual(catalog.lectures[0].slug, "04-mechanisms")
            self.assertEqual(len(catalog.assignments), 1)
            self.assertEqual(catalog.assignments[0].slug, "mechanisms-hw")


if __name__ == "__main__":
    unittest.main()
