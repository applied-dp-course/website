import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SITE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

CHECK_SITE_PATH = SCRIPTS_DIR / "check_site.py"
SPEC = importlib.util.spec_from_file_location("check_site", CHECK_SITE_PATH)
check_site = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_site
SPEC.loader.exec_module(check_site)

content_model = check_site.content_model
write_redirects = check_site.write_redirects


class CheckSiteHelpersTest(unittest.TestCase):
    def test_resolve_internal_relative_link(self) -> None:
        site_root = Path("/site")
        page = site_root / "schedule.html"
        target = check_site.resolve_internal_target(site_root, page, "lectures.html")
        self.assertEqual(target, site_root / "lectures.html")

    def test_resolve_internal_root_relative_link(self) -> None:
        site_root = Path("/site")
        page = site_root / "blog/index.html"
        target = check_site.resolve_internal_target(site_root, page, "/assignments.html")
        self.assertEqual(target, site_root / "assignments.html")

    def test_external_links_are_ignored(self) -> None:
        site_root = Path("/site")
        page = site_root / "index.html"
        self.assertIsNone(
            check_site.resolve_internal_target(
                site_root,
                page,
                "https://colab.research.google.com/github/example/repo/blob/main/notebook.ipynb",
            )
        )


class CheckSiteLocalTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.output_root = self.site_root / "_site"
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.assignments_dir = self.content_dir / "assignments"
        self.offerings_dir = self.content_dir / "offerings"
        self.generated_dir = self.site_root / "generated"
        self.output_root.mkdir()
        self.generated_dir.mkdir()

        lecture_dir = self.lectures_dir / "03-hypothesis_testing"
        lecture_dir.mkdir(parents=True)
        (lecture_dir / "learn.ipynb").write_text("{}", encoding="utf-8")
        (lecture_dir / "slides.qmd").write_text('---\ntitle: Lecture\n---\n', encoding="utf-8")
        (lecture_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Lecture",
                    'number: "03"',
                    "subjects:",
                    "  - testing",
                    "surfaces:",
                    "  learn: learn.ipynb",
                    "  presentation: slides.qmd",
                ]
            ),
            encoding="utf-8",
        )

        assignment_dir = self.assignments_dir / "sample-hw"
        assignment_dir.mkdir(parents=True)
        (assignment_dir / "assignment.ipynb").write_text("{}", encoding="utf-8")
        (assignment_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Sample Assignment",
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

        offering_dir = self.offerings_dir / "2026-fall"
        offering_dir.mkdir(parents=True)
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
        (offering_dir / "offering.yml").write_text(
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
        (offering_dir / "schedule.csv").write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2026-10-20,Lecture,03-hypothesis_testing,03-hypothesis_testing,sample-hw,",
                ]
            ),
            encoding="utf-8",
        )

        self._original_site_root = content_model.SITE_ROOT
        self._original_content_dir = content_model.CONTENT_DIR
        self._original_lectures_dir = content_model.LECTURES_DIR
        self._original_assignments_dir = content_model.ASSIGNMENTS_DIR
        self._original_offerings_dir = content_model.OFFERINGS_DIR

        content_model.SITE_ROOT = self.site_root
        content_model.CONTENT_DIR = self.content_dir
        content_model.LECTURES_DIR = self.lectures_dir
        content_model.ASSIGNMENTS_DIR = self.assignments_dir
        content_model.OFFERINGS_DIR = self.offerings_dir

    def tearDown(self) -> None:
        content_model.SITE_ROOT = self._original_site_root
        content_model.CONTENT_DIR = self._original_content_dir
        content_model.LECTURES_DIR = self._original_lectures_dir
        content_model.ASSIGNMENTS_DIR = self._original_assignments_dir
        content_model.OFFERINGS_DIR = self._original_offerings_dir
        self._temporary_directory.cleanup()

    def _write_minimal_site(self) -> None:
        catalog = content_model.load_catalog()
        for route in check_site.TOP_LEVEL_ROUTES:
            path = self.output_root / route
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<html><body>ok</body></html>", encoding="utf-8")

        learn = (
            self.output_root
            / content_model.LECTURES_URL_PREFIX
            / "03-hypothesis_testing"
            / "learn.html"
        )
        learn.parent.mkdir(parents=True, exist_ok=True)
        learn.write_text("<html>learn</html>", encoding="utf-8")
        slides = learn.with_name("slides.html")
        slides.write_text("<html>slides</html>", encoding="utf-8")

        colab_url = check_site.expected_colab_urls(catalog)[0]
        assignments = self.output_root / "assignments.html"
        assignments.write_text(
            f'<html><body><a href="{colab_url}">Open in Colab</a></body></html>',
            encoding="utf-8",
        )

        gallery_path = self.generated_dir / "gallery.json"
        gallery_path.write_text(
            '{"entries": [{"id": "tool", "title": "Tool", "summary": "", '
            '"source_kind": "standalone", "source_title": "Tool", '
            '"subjects": ["testing"], "runtime": "static", "href": "tools/tool/"}]}',
            encoding="utf-8",
        )
        tool_page = self.output_root / "tools" / "tool" / "index.html"
        tool_page.parent.mkdir(parents=True, exist_ok=True)
        tool_page.write_text("<html>tool</html>", encoding="utf-8")

        for legacy_path, target_path in write_redirects.collect_legacy_redirects(
            catalog,
            output_root=self.output_root,
        ):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("<html>target</html>", encoding="utf-8")
        write_redirects.write_legacy_redirects(catalog, output_root=self.output_root)

    def test_local_site_passes_with_required_routes_and_colab(self) -> None:
        self._write_minimal_site()
        errors = check_site.check_local_site(self.output_root)
        self.assertEqual(errors, [])

    def test_missing_required_route_fails(self) -> None:
        self._write_minimal_site()
        (self.output_root / "archive.html").unlink()
        errors = check_site.check_local_site(self.output_root)
        self.assertTrue(any("missing required route: archive.html" in error for error in errors))

    def test_broken_internal_link_fails(self) -> None:
        self._write_minimal_site()
        schedule = self.output_root / "schedule.html"
        schedule.write_text('<html><body><a href="missing.html">bad</a></body></html>', encoding="utf-8")
        errors = check_site.check_local_site(self.output_root)
        self.assertTrue(any("broken internal" in error for error in errors))

    def test_forbidden_planning_file_fails(self) -> None:
        self._write_minimal_site()
        (self.output_root / "STATUS.md").write_text("secret", encoding="utf-8")
        errors = check_site.check_local_site(self.output_root)
        self.assertTrue(any("STATUS.md" in error for error in errors))


class LiveRepositorySiteCheckTest(unittest.TestCase):
    def test_built_site_passes_local_verification(self) -> None:
        output_root = content_model.SITE_ROOT / "_site"
        if not output_root.is_dir():
            self.skipTest("_site not built")
        errors = check_site.check_local_site(output_root)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
