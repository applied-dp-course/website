import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_content.py"
SPEC = importlib.util.spec_from_file_location("sync_content", SCRIPT_PATH)
sync_content = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = sync_content
SPEC.loader.exec_module(sync_content)

content_model = sync_content.content_model


class SyncContentSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.offerings_dir = self.content_dir / "offerings"

        for path in (
            self.lectures_dir / "02-reconstruction",
            self.lectures_dir / "03-hypothesis_testing",
            self.content_dir / "assignments",
            self.offerings_dir / "2026-fall",
        ):
            path.mkdir(parents=True)

        (self.lectures_dir / "02-reconstruction" / "learn.ipynb").write_text("{}", encoding="utf-8")
        (self.lectures_dir / "02-reconstruction" / "notebook.ipynb").write_text("{}", encoding="utf-8")
        (self.lectures_dir / "02-reconstruction" / "slides.qmd").write_text(
            '---\ntitle: Reconstruction attacks\n---\n',
            encoding="utf-8",
        )
        (self.lectures_dir / "02-reconstruction" / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Reconstruction attacks",
                    'number: "02"',
                    "subjects:",
                    "  - reconstruction attacks",
                    "status: planned",
                    "surfaces:",
                    "  learn: learn.ipynb",
                    "  presentation: notebook.ipynb",
                ]
            ),
            encoding="utf-8",
        )

        (self.lectures_dir / "03-hypothesis_testing" / "learn.ipynb").write_text("{}", encoding="utf-8")
        (self.lectures_dir / "03-hypothesis_testing" / "slides.qmd").write_text(
            '---\ntitle: "DP as Hypothesis Testing"\n---\n',
            encoding="utf-8",
        )
        (self.lectures_dir / "03-hypothesis_testing" / "manifest.yml").write_text(
            "\n".join(
                [
                    'title: "DP as Hypothesis Testing"',
                    'number: "03"',
                    "subjects:",
                    "  - hypothesis testing",
                    "status: planned",
                    "surfaces:",
                    "  learn: learn.ipynb",
                    "  presentation: slides.qmd",
                ]
            ),
            encoding="utf-8",
        )

        (self.content_dir / "course.yml").write_text(
            "\n".join(
                [
                    "title: Applied Differential Privacy",
                    "repo:",
                    "  owner: applied-dp-course",
                    "  name: website",
                    "  branch: main",
                    "current_offering: 2026-fall",
                    "instructors: []",
                    "colab:",
                    "  enabled: true",
                ]
            ),
            encoding="utf-8",
        )
        (self.offerings_dir / "2026-fall" / "offering.yml").write_text(
            "\n".join(
                [
                    "label: Fall 2026",
                    "start_date: 2026-10-20",
                    "end_date: 2027-01-26",
                    "meeting:",
                    "  time: Tuesdays 10:00–12:00",
                    "  place: Room 101",
                ]
            ),
            encoding="utf-8",
        )
        (self.offerings_dir / "2026-fall" / "schedule.csv").write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2026-10-20,Reconstruction attacks,02-reconstruction,02-reconstruction,,",
                    "2,2026-10-27,DP as hypothesis testing,03-hypothesis_testing,03-hypothesis_testing,,",
                    "3,2026-11-03,Reading week,,,,No class",
                ]
            ),
            encoding="utf-8",
        )

        self._write_page_shells()

        self._original_site_root = content_model.SITE_ROOT
        self._original_content_dir = content_model.CONTENT_DIR
        self._original_lectures_dir = content_model.LECTURES_DIR
        self._original_assignments_dir = content_model.ASSIGNMENTS_DIR
        self._original_offerings_dir = content_model.OFFERINGS_DIR
        self._original_tools_dir = content_model.TOOLS_DIR

        content_model.SITE_ROOT = self.site_root
        content_model.CONTENT_DIR = self.content_dir
        content_model.LECTURES_DIR = self.lectures_dir
        content_model.ASSIGNMENTS_DIR = self.content_dir / "assignments"
        content_model.OFFERINGS_DIR = self.offerings_dir
        content_model.TOOLS_DIR = self.site_root / "tools"

    def tearDown(self) -> None:
        content_model.SITE_ROOT = self._original_site_root
        content_model.CONTENT_DIR = self._original_content_dir
        content_model.LECTURES_DIR = self._original_lectures_dir
        content_model.ASSIGNMENTS_DIR = self._original_assignments_dir
        content_model.OFFERINGS_DIR = self._original_offerings_dir
        content_model.TOOLS_DIR = self._original_tools_dir
        self._temporary_directory.cleanup()

    def _write_page_shells(self) -> None:
        for name, section in (
            ("lectures.qmd", sync_content.LECTURES_SECTION),
            ("schedule.qmd", sync_content.SCHEDULE_SECTION),
            ("archive.qmd", sync_content.ARCHIVE_SECTION),
            ("assignments.qmd", sync_content.ASSIGNMENTS_SECTION),
            ("tools.qmd", sync_content.TOOLS_SECTION),
            ("index.qmd", sync_content.OFFERING_BANNER_SECTION),
            ("syllabus.qmd", sync_content.SYLLABUS_LOGISTICS_SECTION),
        ):
            marker_section = f"{section.begin}\nold\n{section.end}\n"
            (self.site_root / name).write_text(marker_section, encoding="utf-8")

    def test_two_uploaded_sources_create_registration_files(self) -> None:
        lecture_dir = self.lectures_dir / "04-new-topic"
        lecture_dir.mkdir()
        (lecture_dir / "deck-source.qmd").write_text(
            '---\ntitle: "New Topic"\nformat: revealjs\n---\n',
            encoding="utf-8",
        )
        (lecture_dir / "study-source.ipynb").write_text(
            json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
            encoding="utf-8",
        )

        sync_content.run_phase("catalog")

        self.assertTrue((lecture_dir / "slides.qmd").exists())
        self.assertTrue((lecture_dir / "learn.ipynb").exists())
        self.assertTrue((lecture_dir / "manifest.yml").exists())
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("04 · New Topic", lectures_page)

    def test_schedule_is_offering_driven(self) -> None:
        sync_content.run_phase("catalog")
        schedule_page = (self.site_root / "schedule.qmd").read_text(encoding="utf-8")
        self.assertIn("| 3 | 2026-11-03 | Reading week |", schedule_page)
        self.assertIn("No class", schedule_page)
        self.assertNotIn("| Status |", schedule_page)

    def test_optional_schedule_cells_render_em_dashes(self) -> None:
        sync_content.run_phase("catalog")
        schedule_page = (self.site_root / "schedule.qmd").read_text(encoding="utf-8")
        reading_row = next(
            line for line in schedule_page.splitlines() if "Reading week" in line
        )
        self.assertEqual(reading_row.count(sync_content.EM_DASH), 3)

    def test_archive_lists_offering(self) -> None:
        sync_content.run_phase("catalog")
        archive_page = (self.site_root / "archive.qmd").read_text(encoding="utf-8")
        self.assertIn("<details>", archive_page)
        self.assertIn("Fall 2026", archive_page)
        self.assertIn("current", archive_page)

    def test_archive_distinguishes_past_and_current_offerings(self) -> None:
        past_dir = self.offerings_dir / "2025-fall"
        past_dir.mkdir()
        (past_dir / "offering.yml").write_text(
            "\n".join(
                [
                    "label: Fall 2025",
                    "start_date: 2025-10-21",
                    "end_date: 2026-01-27",
                    "meeting:",
                    "  time: Tuesdays 10:00–12:00",
                    "  place: ''",
                ]
            ),
            encoding="utf-8",
        )
        (past_dir / "schedule.csv").write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2025-10-21,Kickoff,02-reconstruction,02-reconstruction,,",
                ]
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        archive_page = (self.site_root / "archive.qmd").read_text(encoding="utf-8")
        self.assertIn("Fall 2025", archive_page)
        self.assertIn("Fall 2026 (2026-10-20 – 2027-01-26) — current", archive_page)
        past_section = archive_page.split("<summary><strong>Fall 2025", 1)[1].split(
            "</details>", 1
        )[0]
        self.assertNotIn("— current", past_section)

    def test_lecture_page_lists_interactive_apps(self) -> None:
        manifest = self.lectures_dir / "02-reconstruction" / "manifest.yml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "\nruntimes:\n  apps:\n    - reconstruction-2d-slab\n",
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("apps:", lectures_page)
        self.assertIn("reconstruction-2d-slab", lectures_page)

    def test_offering_switch_updates_banner_and_archive(self) -> None:
        spring_dir = self.offerings_dir / "2027-spring"
        spring_dir.mkdir()
        (spring_dir / "offering.yml").write_text(
            "\n".join(
                [
                    "label: Spring 2027",
                    "start_date: 2027-01-19",
                    "end_date: 2027-05-04",
                    "meeting:",
                    "  time: Wednesdays 14:00–16:00",
                    "  place: Room 202",
                ]
            ),
            encoding="utf-8",
        )
        (spring_dir / "schedule.csv").write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2027-01-19,Reconstruction attacks,02-reconstruction,02-reconstruction,,",
                ]
            ),
            encoding="utf-8",
        )
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8").replace(
                "current_offering: 2026-fall",
                "current_offering: 2027-spring",
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        index_page = (self.site_root / "index.qmd").read_text(encoding="utf-8")
        schedule_page = (self.site_root / "schedule.qmd").read_text(encoding="utf-8")
        archive_page = (self.site_root / "archive.qmd").read_text(encoding="utf-8")
        self.assertIn("Spring 2027", index_page)
        self.assertIn("Wednesdays 14:00–16:00", index_page)
        self.assertIn("2027-01-19", schedule_page)
        self.assertIn("Spring 2027 (2027-01-19 – 2027-05-04) — current", archive_page)
        self.assertNotIn("Fall 2026 — current", archive_page)

    def test_index_banner_uses_offering_metadata(self) -> None:
        sync_content.run_phase("catalog")
        index_page = (self.site_root / "index.qmd").read_text(encoding="utf-8")
        self.assertIn("Fall 2026", index_page)
        self.assertIn("Tuesdays 10:00–12:00", index_page)
        self.assertIn("Room 101", index_page)

    def test_missing_marker_pair_fails(self) -> None:
        (self.site_root / "schedule.qmd").write_text("no markers here\n", encoding="utf-8")
        with self.assertRaises(RuntimeError) as context:
            sync_content.run_phase("catalog")
        self.assertIn("marker pair", str(context.exception))

    def test_duplicate_marker_pair_fails(self) -> None:
        duplicate = (
            f"{sync_content.SCHEDULE_SECTION.begin}\n"
            f"{sync_content.SCHEDULE_SECTION.begin}\n"
            f"{sync_content.SCHEDULE_SECTION.end}\n"
            f"{sync_content.SCHEDULE_SECTION.end}\n"
        )
        (self.site_root / "schedule.qmd").write_text(duplicate, encoding="utf-8")
        with self.assertRaises(RuntimeError) as context:
            sync_content.run_phase("catalog")
        self.assertIn("marker pair", str(context.exception))

    def test_empty_catalog_renders_useful_message(self) -> None:
        import shutil

        shutil.rmtree(self.lectures_dir)
        self.lectures_dir.mkdir()
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2026-10-20,Kickoff,,,,",
                ]
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("No lectures are published", lectures_page)

    def test_generation_is_idempotent(self) -> None:
        sync_content.run_phase("catalog")
        first_pass = {
            path.name: path.read_text(encoding="utf-8")
            for path in (
                self.site_root / "lectures.qmd",
                self.site_root / "schedule.qmd",
                self.site_root / "archive.qmd",
                self.site_root / "index.qmd",
                self.site_root / "generated" / "catalog.json",
            )
        }
        sync_content.run_phase("catalog")
        second_pass = {
            path.name: path.read_text(encoding="utf-8")
            for path in (
                self.site_root / "lectures.qmd",
                self.site_root / "schedule.qmd",
                self.site_root / "archive.qmd",
                self.site_root / "index.qmd",
                self.site_root / "generated" / "catalog.json",
            )
        }
        self.assertEqual(first_pass, second_pass)

    def test_titles_with_punctuation_are_escaped(self) -> None:
        manifest = self.lectures_dir / "03-hypothesis_testing" / "manifest.yml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                'title: "DP as Hypothesis Testing"',
                'title: "DP: Hypothesis & Testing | Part 1"',
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("DP: Hypothesis & Testing \\| Part 1", lectures_page)

    def test_lectures_sort_numerically_within_subject(self) -> None:
        directory = self.lectures_dir / "10-advanced-topic"
        directory.mkdir()
        (directory / "learn.ipynb").write_text("{}", encoding="utf-8")
        (directory / "slides.qmd").write_text(
            '---\ntitle: "Advanced topic"\n---\n',
            encoding="utf-8",
        )
        (directory / "manifest.yml").write_text(
            "\n".join(
                [
                    'title: "Advanced topic"',
                    'number: "10"',
                    "subjects:",
                    "  - hypothesis testing",
                    "status: planned",
                    "surfaces:",
                    "  learn: learn.ipynb",
                    "  presentation: slides.qmd",
                ]
            ),
            encoding="utf-8",
        )

        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        hypothesis_section = lectures_page.split("### hypothesis testing", 1)[1].split("###", 1)[0]
        positions = [
            hypothesis_section.index("03 · DP as Hypothesis Testing"),
            hypothesis_section.index("10 · Advanced topic"),
        ]
        self.assertLess(positions[0], positions[1])

    def test_catalog_json_is_written(self) -> None:
        sync_content.run_phase("catalog")
        catalog_path = self.site_root / "generated" / "catalog.json"
        self.assertTrue(catalog_path.exists())
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["course"]["current_offering"], "2026-fall")
        self.assertEqual(len(payload["lectures"]), 2)
        self.assertEqual(len(payload["offerings"]), 1)
        self.assertEqual(payload["offerings"][0]["schedule"][0]["week"], "1")

    def test_generated_links_use_content_lectures_prefix(self) -> None:
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("content/lectures/02-reconstruction/notebook.ipynb", lectures_page)
        self.assertIn("content/lectures/03-hypothesis_testing/learn.ipynb", lectures_page)

    def test_index_banner_has_blank_line_before_bullet_list(self) -> None:
        sync_content.run_phase("catalog")
        banner = sync_content.render_offering_banner(content_model.load_catalog())
        self.assertIn("**Fall 2026**\n\n- **Dates:**", banner)
        index_page = (self.site_root / "index.qmd").read_text(encoding="utf-8")
        self.assertIn("**Fall 2026**\n\n- **Dates:**", index_page)

    def test_syllabus_logistics_use_offering_metadata(self) -> None:
        (self.offerings_dir / "2026-fall" / "offering.yml").write_text(
            "\n".join(
                [
                    "label: Fall 2026",
                    "start_date: 2026-10-20",
                    "end_date: 2027-01-26",
                    "meeting:",
                    "  time: Tuesdays 10:00–12:00",
                    "  place: Room 101",
                    "staff:",
                    "  - name: Alex Example",
                    "    role: TA",
                    "announcements:",
                    "  - date: 2026-10-01",
                    "    text: Welcome to the course",
                    "grading_notes: Problem sets are due Tuesdays at noon.",
                ]
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        syllabus_page = (self.site_root / "syllabus.qmd").read_text(encoding="utf-8")
        self.assertIn("### Fall 2026", syllabus_page)
        self.assertIn("Room 101", syllabus_page)
        self.assertIn("Alex Example", syllabus_page)
        self.assertIn("Welcome to the course", syllabus_page)
        self.assertIn("Problem sets are due Tuesdays at noon.", syllabus_page)


class SyncGalleryPageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        (self.site_root / "tools.qmd").write_text(
            f"{sync_content.TOOLS_SECTION.begin}\nold\n{sync_content.TOOLS_SECTION.end}\n",
            encoding="utf-8",
        )
        gallery_payload = {
            "entries": [
                {
                    "id": "reconstruction-2d-slab",
                    "title": "2-D reconstruction slab",
                    "summary": "",
                    "source_kind": "lecture",
                    "source_title": "Reconstruction attacks",
                    "source_lecture_number": "02",
                    "subjects": ["reconstruction attacks"],
                    "runtime": "browser-native",
                    "href": "content/lectures/02-reconstruction/apps/reconstruction-2d-slab/",
                },
                {
                    "id": "privacy-tradeoff-explorer",
                    "title": "Privacy Tradeoff Explorer",
                    "summary": "Explore privacy tradeoffs.",
                    "source_kind": "standalone",
                    "source_title": "Privacy Tradeoff Explorer",
                    "subjects": ["hypothesis testing"],
                    "runtime": "static",
                    "href": "tools/privacy-tradeoff-explorer/",
                },
            ]
        }
        generated_dir = self.site_root / "generated"
        generated_dir.mkdir()
        (generated_dir / "gallery.json").write_text(
            json.dumps(gallery_payload, indent=2),
            encoding="utf-8",
        )

        self._original_site_root = content_model.SITE_ROOT
        content_model.SITE_ROOT = self.site_root

    def tearDown(self) -> None:
        content_model.SITE_ROOT = self._original_site_root
        self._temporary_directory.cleanup()

    def test_gallery_phase_groups_tools_by_subject(self) -> None:
        sync_content.run_phase("gallery")
        tools_page = (self.site_root / "tools.qmd").read_text(encoding="utf-8")
        self.assertIn("### hypothesis testing", tools_page)
        self.assertIn("Privacy Tradeoff Explorer", tools_page)
        self.assertIn("standalone", tools_page)
        self.assertIn("### reconstruction attacks", tools_page)
        self.assertIn("from Lecture 02 · Reconstruction attacks", tools_page)

    def test_gallery_phase_fails_without_gallery_json(self) -> None:
        (self.site_root / "generated" / "gallery.json").unlink()
        with self.assertRaises(RuntimeError) as context:
            sync_content.run_phase("gallery")
        self.assertIn("gallery.json", str(context.exception))


class LiveRepositorySyncContentTest(unittest.TestCase):
    def test_repository_sync_runs(self) -> None:
        sync_content.run_phase("catalog")

    def test_repository_gallery_sync_runs(self) -> None:
        gallery_path = content_model.SITE_ROOT / "generated" / "gallery.json"
        if not gallery_path.exists():
            self.skipTest("generated/gallery.json not built")
        sync_content.run_phase("gallery")
        tools_page = (content_model.SITE_ROOT / "tools.qmd").read_text(encoding="utf-8")
        self.assertIn("privacy-tradeoff-explorer", tools_page.lower())


if __name__ == "__main__":
    unittest.main()
