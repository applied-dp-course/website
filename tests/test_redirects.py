import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "write_redirects.py"
SPEC = importlib.util.spec_from_file_location("write_redirects", SCRIPT_PATH)
write_redirects = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = write_redirects
SPEC.loader.exec_module(write_redirects)

content_model = write_redirects.content_model


class WriteRedirectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.offerings_dir = self.content_dir / "offerings"

        for path in (
            self.lectures_dir / "02-reconstruction",
            self.lectures_dir / "03-hypothesis_testing",
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

        self.output_root = self.site_root / "_site"
        self._original_site_root = content_model.SITE_ROOT
        self._original_content_dir = content_model.CONTENT_DIR
        self._original_lectures_dir = content_model.LECTURES_DIR
        self._original_offerings_dir = content_model.OFFERINGS_DIR

        content_model.SITE_ROOT = self.site_root
        content_model.CONTENT_DIR = self.content_dir
        content_model.LECTURES_DIR = self.lectures_dir
        content_model.OFFERINGS_DIR = self.offerings_dir

    def tearDown(self) -> None:
        content_model.SITE_ROOT = self._original_site_root
        content_model.CONTENT_DIR = self._original_content_dir
        content_model.LECTURES_DIR = self._original_lectures_dir
        content_model.OFFERINGS_DIR = self._original_offerings_dir
        self._temporary_directory.cleanup()

    def _write_target_pages(self) -> None:
        catalog = content_model.load_catalog()
        for legacy_path, target_path in write_redirects.collect_legacy_redirects(
            catalog,
            output_root=self.output_root,
        ):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("<html>target</html>", encoding="utf-8")

    def test_collects_legacy_surface_and_app_routes(self) -> None:
        catalog = content_model.load_catalog()
        pairs = write_redirects.collect_legacy_redirects(catalog, output_root=self.output_root)
        legacy_paths = {
            legacy.relative_to(self.output_root).as_posix() for legacy, _ in pairs
        }
        self.assertIn("lectures/02-reconstruction/learn.html", legacy_paths)
        self.assertIn("lectures/02-reconstruction/notebook.html", legacy_paths)
        self.assertIn("lectures/02-reconstruction/slides.html", legacy_paths)
        self.assertIn(
            "lectures/02-reconstruction/apps/reconstruction-2d-slab/index.html",
            legacy_paths,
        )
        self.assertIn("lectures/03-hypothesis_testing/learn.html", legacy_paths)
        self.assertIn("lectures/03-hypothesis_testing/slides.html", legacy_paths)

    def test_redirect_target_existence(self) -> None:
        self._write_target_pages()
        catalog = content_model.load_catalog()
        written = write_redirects.write_legacy_redirects(
            catalog,
            output_root=self.output_root,
        )
        self.assertGreaterEqual(len(written), 5)
        legacy, target = written[0]
        self.assertTrue(legacy.is_file())
        self.assertTrue(target.is_file())
        self.assertIn(write_redirects.REDIRECT_MARKER, legacy.read_text(encoding="utf-8"))

    def test_missing_target_fails(self) -> None:
        catalog = content_model.load_catalog()
        with self.assertRaises(RuntimeError) as context:
            write_redirects.write_legacy_redirects(catalog, output_root=self.output_root)
        self.assertIn("redirect target missing", str(context.exception))

    def test_refuses_to_overwrite_real_output_file(self) -> None:
        self._write_target_pages()
        catalog = content_model.load_catalog()
        legacy_path = self.output_root / "lectures/02-reconstruction/learn.html"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text("<html>real page</html>", encoding="utf-8")
        with self.assertRaises(RuntimeError) as context:
            write_redirects.write_legacy_redirects(catalog, output_root=self.output_root)
        self.assertIn("refusing to overwrite rendered page", str(context.exception))

    def test_old_route_fixture_maps_to_new_route(self) -> None:
        self._write_target_pages()
        catalog = content_model.load_catalog()
        write_redirects.write_legacy_redirects(catalog, output_root=self.output_root)

        legacy_notebook = self.output_root / "lectures/02-reconstruction/notebook.html"
        target_notebook = (
            self.output_root / "content/lectures/02-reconstruction/notebook.html"
        )
        self.assertTrue(legacy_notebook.is_file())
        self.assertTrue(target_notebook.is_file())
        redirect_html = legacy_notebook.read_text(encoding="utf-8")
        self.assertIn("../../content/lectures/02-reconstruction/notebook.html", redirect_html)


class LiveRepositoryRedirectsTest(unittest.TestCase):
    def test_repository_catalog_has_legacy_redirect_pairs(self) -> None:
        catalog = content_model.load_catalog()
        pairs = write_redirects.collect_legacy_redirects(
            catalog,
            output_root=content_model.SITE_ROOT / "_site",
        )
        legacy_paths = {legacy.name for legacy, _ in pairs}
        self.assertIn("learn.html", legacy_paths)
        self.assertIn("notebook.html", legacy_paths)


if __name__ == "__main__":
    unittest.main()
