import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


RUN_SMOKE_PATH = Path(__file__).resolve().parents[1] / "tests" / "run_smoke_tests.py"
SPEC = importlib.util.spec_from_file_location("run_smoke_tests", RUN_SMOKE_PATH)
run_smoke_tests = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = run_smoke_tests
SPEC.loader.exec_module(run_smoke_tests)

content_model = run_smoke_tests.content_model


class DiscoverCanvasAppsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.offerings_dir = self.content_dir / "offerings"
        self.assignments_dir = self.content_dir / "assignments"
        self.output_root = self.site_root / "_site"

        self.assignments_dir.mkdir(parents=True)

        lecture_dir = self.lectures_dir / "02-reconstruction"
        lecture_dir.mkdir(parents=True)
        (lecture_dir / "learn.ipynb").write_text("{}", encoding="utf-8")
        (lecture_dir / "notebook.ipynb").write_text("{}", encoding="utf-8")
        (lecture_dir / "manifest.yml").write_text(
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
                    "    - reconstruction-3d-slabs",
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
        (self.offerings_dir / "2026-fall").mkdir(parents=True)
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
                ]
            ),
            encoding="utf-8",
        )

        for app_id in ("reconstruction-2d-slab", "reconstruction-3d-slabs"):
            app_dir = (
                self.output_root
                / content_model.LECTURES_URL_PREFIX
                / "02-reconstruction"
                / "apps"
                / app_id
            )
            app_dir.mkdir(parents=True)
            (app_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        generated_dir = self.site_root / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        (generated_dir / "gallery.json").write_text(
            "\n".join(
                [
                    "{",
                    '  "entries": [',
                    "    {",
                    '      "id": "reconstruction-2d-slab",',
                    '      "title": "2D slab",',
                    '      "summary": "",',
                    '      "source_kind": "lecture",',
                    '      "source_title": "Reconstruction attacks",',
                    '      "source_lecture_number": "02",',
                    '      "subjects": ["reconstruction attacks"],',
                    '      "runtime": "browser-native",',
                    '      "href": "content/lectures/02-reconstruction/apps/reconstruction-2d-slab/"',
                    "    },",
                    "    {",
                    '      "id": "reconstruction-3d-slabs",',
                    '      "title": "3D slabs",',
                    '      "summary": "",',
                    '      "source_kind": "lecture",',
                    '      "source_title": "Reconstruction attacks",',
                    '      "source_lecture_number": "02",',
                    '      "subjects": ["reconstruction attacks"],',
                    '      "runtime": "browser-native",',
                    '      "href": "content/lectures/02-reconstruction/apps/reconstruction-3d-slabs/"',
                    "    }",
                    "  ]",
                    "}",
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

    def test_discovers_browser_native_apps_from_gallery(self) -> None:
        _wasm_paths, canvas_paths = run_smoke_tests.discover_smoke_targets(
            self.site_root,
            self.output_root,
        )
        self.assertEqual(
            canvas_paths,
            [
                "content/lectures/02-reconstruction/apps/reconstruction-2d-slab",
                "content/lectures/02-reconstruction/apps/reconstruction-3d-slabs",
            ],
        )

    def test_missing_canvas_app_fails_fast(self) -> None:
        missing = (
            self.output_root
            / content_model.LECTURES_URL_PREFIX
            / "02-reconstruction"
            / "apps"
            / "reconstruction-3d-slabs"
            / "index.html"
        )
        missing.unlink()
        with self.assertRaises(SystemExit) as context:
            run_smoke_tests.discover_smoke_targets(self.site_root, self.output_root)
        self.assertIn("expected built canvas app missing", str(context.exception))


class LiveRepositoryWasmDiscoveryTest(unittest.TestCase):
    def test_repository_discovers_unique_wasm_smoke_targets(self) -> None:
        output_root = content_model.SITE_ROOT / "_site"
        if not output_root.is_dir():
            self.skipTest("_site not built")
        uses = run_smoke_tests.build_interactives.discover_interactives(
            content_model.SITE_ROOT
        )
        wasm_paths = run_smoke_tests.discover_wasm_app_paths(
            content_model.SITE_ROOT, output_root
        )
        self.assertEqual(len(wasm_paths), 2)
        self.assertTrue(
            any(path.endswith("privacy-plot-norm-6197737a49") for path in wasm_paths)
        )
        self.assertTrue(
            any("privacy-plot-norm-laplace-uniform-" in path for path in wasm_paths)
        )
        self.assertTrue(
            all(path.startswith("content/lectures/") for path in wasm_paths)
        )
        home_uses = [
            use
            for use in uses
            if use.source.relative_to(content_model.SITE_ROOT).as_posix() == "index.qmd"
        ]
        self.assertEqual(len(home_uses), 1)


class DedupeWasmSmokePathsTest(unittest.TestCase):
    def test_prefers_lecture_path_for_duplicate_artifact(self) -> None:
        paths = run_smoke_tests.dedupe_wasm_smoke_paths(
            [
                "apps/privacy-plot-norm-6197737a49",
                "blog/posts/example/apps/privacy-plot-norm-6197737a49",
                "content/lectures/03-hypothesis_testing/apps/privacy-plot-norm-6197737a49",
            ]
        )
        self.assertEqual(
            paths,
            ["content/lectures/03-hypothesis_testing/apps/privacy-plot-norm-6197737a49"],
        )


class LiveRepositoryCanvasDiscoveryTest(unittest.TestCase):
    def test_repository_has_two_canvas_apps(self) -> None:
        output_root = content_model.SITE_ROOT / "_site"
        if not output_root.is_dir():
            self.skipTest("_site not built")
        _wasm_paths, canvas_paths = run_smoke_tests.discover_smoke_targets(
            content_model.SITE_ROOT,
            output_root,
        )
        self.assertEqual(len(canvas_paths), 2)


if __name__ == "__main__":
    unittest.main()
