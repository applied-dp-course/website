import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SYNC_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_content.py"
SPEC = importlib.util.spec_from_file_location("sync_content", SYNC_PATH)
sync_content = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = sync_content
SPEC.loader.exec_module(sync_content)

content_model = sync_content.content_model


class AssignmentsPageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.assignments_dir = self.content_dir / "assignments"
        self.tools_dir = self.site_root / "tools"
        self.offerings_dir = self.content_dir / "offerings"

        self.tools_dir.mkdir(parents=True, exist_ok=True)

        for path in (
            self.lectures_dir / "03-hypothesis_testing",
            self.assignments_dir / "hypothesis-testing-hw",
            self.offerings_dir / "2026-fall",
        ):
            path.mkdir(parents=True)

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

        (self.assignments_dir / "hypothesis-testing-hw" / "assignment.ipynb").write_text(
            "{}",
            encoding="utf-8",
        )
        (self.assignments_dir / "hypothesis-testing-hw" / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Hypothesis Testing Assignment",
                    "subjects:",
                    "  - hypothesis testing",
                    "estimated_time: 120 minutes",
                    "notebook: assignment.ipynb",
                    "related_lectures:",
                    "  - 03-hypothesis_testing",
                    "status: published",
                ]
            ),
            encoding="utf-8",
        )
        (self.assignments_dir / "hypothesis-testing-hw" / "solution.ipynb").write_text(
            "{}",
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
                    "2,2026-10-27,DP as hypothesis testing,03-hypothesis_testing,03-hypothesis_testing,hypothesis-testing-hw,",
                ]
            ),
            encoding="utf-8",
        )

        marker = (
            f"{sync_content.ASSIGNMENTS_SECTION.begin}\nold\n"
            f"{sync_content.ASSIGNMENTS_SECTION.end}\n"
        )
        (self.site_root / "assignments.qmd").write_text(marker, encoding="utf-8")
        for name, section in (
            ("lectures.qmd", sync_content.LECTURES_SECTION),
            ("schedule.qmd", sync_content.SCHEDULE_SECTION),
            ("archive.qmd", sync_content.ARCHIVE_SECTION),
            ("index.qmd", sync_content.OFFERING_BANNER_SECTION),
        ):
            (self.site_root / name).write_text(
                f"{section.begin}\nold\n{section.end}\n",
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

    def test_assignments_page_groups_by_subject_with_due_week(self) -> None:
        sync_content.run_phase("catalog")
        assignments_page = (self.site_root / "assignments.qmd").read_text(encoding="utf-8")
        self.assertIn("### hypothesis testing", assignments_page)
        self.assertIn("Hypothesis Testing Assignment", assignments_page)
        self.assertIn("Week 2 (2026-10-27)", assignments_page)
        self.assertIn("120 minutes", assignments_page)
        self.assertIn("03 · DP as Hypothesis Testing", assignments_page)

    def test_schedule_links_assignment_with_colab_badge(self) -> None:
        sync_content.run_phase("catalog")
        schedule_page = (self.site_root / "schedule.qmd").read_text(encoding="utf-8")
        self.assertIn("Hypothesis Testing Assignment", schedule_page)
        self.assertIn("content/assignments/hypothesis-testing-hw/assignment.ipynb", schedule_page)
        self.assertIn("colab.research.google.com/assets/colab-badge.svg", schedule_page)

    def test_lectures_page_includes_colab_badge(self) -> None:
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertIn("colab.research.google.com/assets/colab-badge.svg", lectures_page)
        self.assertIn("content/lectures/03-hypothesis_testing/learn.ipynb", lectures_page)

    def test_unscheduled_assignment_shows_em_dash_due_date(self) -> None:
        unscheduled_dir = self.assignments_dir / "extra-hw"
        unscheduled_dir.mkdir()
        (unscheduled_dir / "assignment.ipynb").write_text("{}", encoding="utf-8")
        (unscheduled_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Extra Assignment",
                    "subjects:",
                    "  - hypothesis testing",
                    "notebook: assignment.ipynb",
                    "related_lectures:",
                    "  - 03-hypothesis_testing",
                    "status: published",
                ]
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        assignments_page = (self.site_root / "assignments.qmd").read_text(encoding="utf-8")
        extra_section = assignments_page.split("Extra Assignment", 1)[1]
        self.assertIn(f"due {sync_content.EM_DASH}", extra_section)

    def test_assignment_scheduled_multiple_times_lists_all_weeks(self) -> None:
        schedule_path = self.offerings_dir / "2026-fall" / "schedule.csv"
        schedule_path.write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "2,2026-10-27,DP as hypothesis testing,03-hypothesis_testing,03-hypothesis_testing,hypothesis-testing-hw,",
                    "3,2026-11-03,Follow-up,,,,",
                    "4,2026-11-10,Review,,,hypothesis-testing-hw,",
                ]
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        assignments_page = (self.site_root / "assignments.qmd").read_text(encoding="utf-8")
        self.assertIn("Week 2 (2026-10-27); Week 4 (2026-11-10)", assignments_page)

    def test_colab_disabled_omits_badges(self) -> None:
        course_path = self.content_dir / "course.yml"
        course_path.write_text(
            course_path.read_text(encoding="utf-8").replace(
                "enabled: true",
                "enabled: false",
            ),
            encoding="utf-8",
        )
        sync_content.run_phase("catalog")
        lectures_page = (self.site_root / "lectures.qmd").read_text(encoding="utf-8")
        self.assertNotIn("colab.research.google.com/assets/colab-badge.svg", lectures_page)

    def test_solution_notebook_is_excluded_from_publication_checks(self) -> None:
        sync_content.run_phase("catalog")
        assignments_page = (self.site_root / "assignments.qmd").read_text(encoding="utf-8")
        self.assertNotIn("solution.ipynb", assignments_page)
        solution_html = self.site_root / "_site" / "content" / "assignments" / "hypothesis-testing-hw" / "solution.html"
        self.assertFalse(solution_html.exists())


class LiveRepositoryAssignmentsTest(unittest.TestCase):
    def test_repository_catalog_includes_assignment(self) -> None:
        catalog = content_model.load_catalog()
        slugs = {assignment.slug for assignment in catalog.assignments}
        self.assertIn("hypothesis-testing-hw", slugs)

    def test_repository_sync_generates_assignments_page(self) -> None:
        sync_content.run_phase("catalog")
        assignments_page = (content_model.SITE_ROOT / "assignments.qmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("Hypothesis Testing Assignment", assignments_page)
        self.assertIn("Week 2 (2026-10-27)", assignments_page)


if __name__ == "__main__":
    unittest.main()
