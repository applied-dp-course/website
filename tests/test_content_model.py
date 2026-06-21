import importlib.util
import sys
import tempfile
import unittest
import warnings
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "content_model.py"
SPEC = importlib.util.spec_from_file_location("content_model", SCRIPT_PATH)
content_model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = content_model
SPEC.loader.exec_module(content_model)


class ContentModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.assignments_dir = self.content_dir / "assignments"
        self.offerings_dir = self.content_dir / "offerings"
        self.tools_dir = self.site_root / "tools"

        for path in (
            self.lectures_dir / "02-reconstruction",
            self.lectures_dir / "03-hypothesis_testing",
            self.assignments_dir,
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
                    "runtimes:",
                    "  apps:",
                    "    - reconstruction-2d-slab",
                ]
            ),
            encoding="utf-8",
        )

        (self.lectures_dir / "03-hypothesis_testing" / "learn.ipynb").write_text("{}", encoding="utf-8")
        (self.lectures_dir / "03-hypothesis_testing" / "slides.qmd").write_text(
            '---\ntitle: DP as Hypothesis Testing\n---\n',
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
                    "  place: ''",
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
                ]
            ),
            encoding="utf-8",
        )

        self._original_site_root = content_model.SITE_ROOT
        self._original_content_dir = content_model.CONTENT_DIR
        self._original_lectures_dir = content_model.LECTURES_DIR
        self._original_assignments_dir = content_model.ASSIGNMENTS_DIR
        self._original_offerings_dir = content_model.OFFERINGS_DIR
        self._original_tools_dir = content_model.TOOLS_DIR

        content_model.SITE_ROOT = self.site_root
        content_model.CONTENT_DIR = self.content_dir
        content_model.LECTURES_DIR = self.lectures_dir
        content_model.ASSIGNMENTS_DIR = self.assignments_dir
        content_model.OFFERINGS_DIR = self.offerings_dir
        content_model.TOOLS_DIR = self.tools_dir

    def tearDown(self) -> None:
        content_model.SITE_ROOT = self._original_site_root
        content_model.CONTENT_DIR = self._original_content_dir
        content_model.LECTURES_DIR = self._original_lectures_dir
        content_model.ASSIGNMENTS_DIR = self._original_assignments_dir
        content_model.OFFERINGS_DIR = self._original_offerings_dir
        content_model.TOOLS_DIR = self._original_tools_dir
        self._temporary_directory.cleanup()

    def test_valid_course_and_offering_load(self) -> None:
        catalog = content_model.load_catalog()
        self.assertEqual(catalog.course.title, "Applied Differential Privacy")
        self.assertEqual(catalog.course.current_offering, "2026-fall")
        self.assertEqual(len(catalog.offerings), 1)
        self.assertEqual(len(catalog.lectures), 2)
        self.assertEqual(catalog.lectures[0].slug, "02-reconstruction")
        self.assertEqual(catalog.lectures[1].slug, "03-hypothesis_testing")

    def test_missing_current_offering_fails(self) -> None:
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8").replace("2026-fall", "2027-spring"),
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_course()
        self.assertIn("current_offering", str(context.exception))

    def test_malformed_date_fails(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            schedule_path.read_text(encoding="utf-8").replace("2026-10-20", "Oct 20 2026"),
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_catalog()
        self.assertIn("date", str(context.exception))

    def test_duplicate_week_fails(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2026-10-20,Reconstruction attacks,02-reconstruction,02-reconstruction,,",
                    "1,2026-10-27,Duplicate week,03-hypothesis_testing,03-hypothesis_testing,,",
                ]
            ),
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_catalog()
        self.assertIn("duplicate week", str(context.exception))

    def test_unknown_lecture_reference_fails(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            schedule_path.read_text(encoding="utf-8").replace(
                "03-hypothesis_testing",
                "99-unknown",
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_catalog()
        self.assertIn("unknown lecture slug", str(context.exception))

    def test_unknown_assignment_reference_fails(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            schedule_path.read_text(encoding="utf-8")
            + "\n3,2026-11-03,Reading week,,,missing-assignment,No class",
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_catalog()
        self.assertIn("unknown assignment slug", str(context.exception))

    def test_empty_optional_schedule_cells_are_allowed(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
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
        catalog = content_model.load_catalog()
        reading_week = catalog.offerings[0].rows[-1]
        self.assertIsNone(reading_week.lecture)
        self.assertIsNone(reading_week.presentation)
        self.assertIsNone(reading_week.assignment)
        self.assertEqual(reading_week.notes, "No class")

    def test_stable_ordering(self) -> None:
        catalog = content_model.load_catalog()
        self.assertEqual(
            [lecture.number for lecture in catalog.lectures],
            ["02", "03"],
        )
        self.assertEqual(
            [row.week for row in catalog.offerings[0].rows],
            ["1", "2"],
        )

    def test_empty_instructor_name_fails(self) -> None:
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8").replace(
                "instructors: []",
                "instructors:\n  - name: ''\n    url: ''",
            ),
            encoding="utf-8",
        )
        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.load_course()
        self.assertIn("instructors[0].name", str(context.exception))

    def test_unknown_top_level_course_key_warns(self) -> None:
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8") + "\nfuture_field: true\n",
            encoding="utf-8",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            content_model.load_course()
        self.assertTrue(any("future_field" in str(item.message) for item in caught))

    def test_current_offering_schedule_lookup(self) -> None:
        catalog = content_model.load_catalog()
        schedule = content_model.current_offering_schedule(catalog)
        self.assertEqual(schedule.offering.term, "2026-fall")
        self.assertEqual(len(schedule.rows), 2)

    def test_mixed_week_identifiers_sort_without_error(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "2,2026-10-27,DP as hypothesis testing,03-hypothesis_testing,03-hypothesis_testing,,",
                    "reading,2026-11-03,Reading week,,,,No class",
                    "1,2026-10-20,Reconstruction attacks,02-reconstruction,02-reconstruction,,",
                ]
            ),
            encoding="utf-8",
        )
        catalog = content_model.load_catalog()
        self.assertEqual(
            [row.week for row in catalog.offerings[0].rows],
            ["1", "2", "reading"],
        )

    def test_colab_enabled_false_string(self) -> None:
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8").replace(
                "enabled: true",
                'enabled: "false"',
            ),
            encoding="utf-8",
        )
        course = content_model.load_course()
        self.assertFalse(course.colab.enabled)

    def test_gallery_false_string(self) -> None:
        tool_dir = self.tools_dir / "sample-tool"
        tool_dir.mkdir(parents=True)
        (tool_dir / "index.qmd").write_text("# Tool\n", encoding="utf-8")
        (tool_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Sample Tool",
                    "entrypoint: index.qmd",
                    'runtime: static',
                    'gallery: "false"',
                ]
            ),
            encoding="utf-8",
        )
        tools = content_model.discover_tools(self.tools_dir)
        self.assertEqual(len(tools), 1)
        self.assertFalse(tools[0].gallery)

    def test_assignment_validation_uses_passed_lectures_dir(self) -> None:
        alt_lectures = self.site_root / "alt-lectures" / "03-hypothesis_testing"
        alt_lectures.mkdir(parents=True)
        (alt_lectures / "learn.ipynb").write_text("{}", encoding="utf-8")
        (alt_lectures / "slides.qmd").write_text(
            '---\ntitle: "DP as Hypothesis Testing"\n---\n',
            encoding="utf-8",
        )
        (alt_lectures / "manifest.yml").write_text(
            "\n".join(
                [
                    'title: "DP as Hypothesis Testing"',
                    "surfaces:",
                    "  learn: learn.ipynb",
                    "  presentation: slides.qmd",
                ]
            ),
            encoding="utf-8",
        )

        assignment_dir = self.assignments_dir / "test-hw"
        assignment_dir.mkdir()
        (assignment_dir / "assignment.ipynb").write_text("{}", encoding="utf-8")
        (assignment_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Test Assignment",
                    "subjects:",
                    "  - testing",
                    "notebook: assignment.ipynb",
                    "related_lectures:",
                    "  - 03-hypothesis_testing",
                    "status: published",
                ]
            ),
            encoding="utf-8",
        )

        import shutil

        shutil.rmtree(self.lectures_dir / "03-hypothesis_testing")

        with self.assertRaises(content_model.ContentValidationError) as context:
            content_model.discover_assignments(self.assignments_dir)
        self.assertIn("unknown lecture slug", str(context.exception))

        assignments = content_model.discover_assignments(
            self.assignments_dir,
            lectures_dir=self.site_root / "alt-lectures",
        )
        self.assertEqual(len(assignments), 1)

    def test_lecture_surfaces_resolve_under_content_lectures(self) -> None:
        catalog = content_model.load_catalog()
        reconstruction = catalog.lectures[0]
        self.assertEqual(reconstruction.surfaces.learn, "learn.ipynb")
        self.assertEqual(reconstruction.surfaces.presentation, "notebook.ipynb")
        hypothesis = catalog.lectures[1]
        self.assertEqual(hypothesis.surfaces.learn, "learn.ipynb")
        self.assertEqual(hypothesis.surfaces.presentation, "slides.qmd")

    def test_main_validates_catalog(self) -> None:
        content_model.main()


class LiveRepositoryContentModelTest(unittest.TestCase):
    def test_repository_catalog_loads(self) -> None:
        catalog = content_model.load_catalog()
        self.assertEqual(catalog.course.current_offering, "2026-fall")
        self.assertGreaterEqual(len(catalog.lectures), 2)


if __name__ == "__main__":
    unittest.main()
