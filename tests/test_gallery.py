import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SITE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

GALLERY_PATH = SCRIPTS_DIR / "gallery.py"
SPEC = importlib.util.spec_from_file_location("gallery", GALLERY_PATH)
gallery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gallery
SPEC.loader.exec_module(gallery)

content_model = gallery.content_model


class GalleryBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self._temporary_directory.name)
        self.content_dir = self.site_root / "content"
        self.lectures_dir = self.content_dir / "lectures"
        self.tools_dir = self.site_root / "tools"
        self.assignments_dir = self.content_dir / "assignments"
        self.offerings_dir = self.content_dir / "offerings"

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

    def _write_minimal_offering(self) -> None:
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
                    "  enabled: false",
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
                    "  place: Room 101",
                ]
            ),
            encoding="utf-8",
        )
        (offering_dir / "schedule.csv").write_text(
            "\n".join(
                [
                    "week,date,topic,lecture,presentation,assignment,notes",
                    "1,2026-10-20,Kickoff,,,,",
                ]
            ),
            encoding="utf-8",
        )

    def test_builds_entries_from_lecture_manifests_and_tools(self) -> None:
        self._write_minimal_offering()
        lecture_dir = self.lectures_dir / "02-reconstruction"
        lecture_dir.mkdir(parents=True)
        (lecture_dir / "learn.ipynb").write_text("{}", encoding="utf-8")
        (lecture_dir / "notebook.ipynb").write_text("{}", encoding="utf-8")
        app_dir = lecture_dir / "apps" / "reconstruction-2d-slab"
        app_dir.mkdir(parents=True)
        (app_dir / "index.html").write_text("<html></html>", encoding="utf-8")
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
                ]
            ),
            encoding="utf-8",
        )

        tool_dir = self.tools_dir / "privacy-tradeoff-explorer"
        tool_dir.mkdir(parents=True)
        (tool_dir / "index.qmd").write_text("# Tool\n", encoding="utf-8")
        (tool_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Privacy Tradeoff Explorer",
                    "summary: Explore privacy tradeoffs.",
                    "entrypoint: index.qmd",
                    "subjects:",
                    "  - hypothesis testing",
                    "runtime: wasm-marimo",
                    "gallery: true",
                ]
            ),
            encoding="utf-8",
        )

        catalog = content_model.load_catalog()
        entries = gallery.build_gallery_entries(catalog)
        ids = {entry.id for entry in entries}
        self.assertIn("reconstruction-2d-slab", ids)
        self.assertIn("privacy-tradeoff-explorer", ids)

        lecture_entry = next(entry for entry in entries if entry.id == "reconstruction-2d-slab")
        self.assertEqual(lecture_entry.source_kind, "lecture")
        self.assertEqual(lecture_entry.runtime, "browser-native")
        self.assertEqual(
            lecture_entry.href,
            "content/lectures/02-reconstruction/apps/reconstruction-2d-slab/",
        )

        tool_entry = next(entry for entry in entries if entry.id == "privacy-tradeoff-explorer")
        self.assertEqual(tool_entry.source_kind, "standalone")
        self.assertEqual(tool_entry.runtime, "wasm-marimo")
        self.assertEqual(tool_entry.href, "tools/privacy-tradeoff-explorer/")

    def test_duplicate_gallery_id_fails(self) -> None:
        self._write_minimal_offering()
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
                    "    - shared-id",
                ]
            ),
            encoding="utf-8",
        )
        tool_dir = self.tools_dir / "shared-id"
        tool_dir.mkdir(parents=True)
        (tool_dir / "index.qmd").write_text("# Tool\n", encoding="utf-8")
        (tool_dir / "manifest.yml").write_text(
            "\n".join(
                [
                    "title: Conflicting Tool",
                    "entrypoint: index.qmd",
                    "runtime: static",
                    "gallery: true",
                ]
            ),
            encoding="utf-8",
        )

        catalog = content_model.load_catalog()
        with self.assertRaises(gallery.GalleryError) as context:
            gallery.build_gallery_entries(catalog)
        self.assertIn("duplicate gallery id", str(context.exception))

    def test_missing_entrypoint_fails(self) -> None:
        self._write_minimal_offering()
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
                ]
            ),
            encoding="utf-8",
        )
        catalog = content_model.load_catalog()
        entries = gallery.build_gallery_entries(catalog)
        with self.assertRaises(gallery.GalleryError) as context:
            gallery.write_gallery_json(
                entries,
                self.site_root / "generated" / "gallery.json",
                site_root=self.site_root,
            )
        self.assertIn("missing", str(context.exception))

    def test_write_and_load_roundtrip(self) -> None:
        entries = (
            gallery.GalleryEntry(
                id="demo",
                title="Demo Tool",
                summary="A demo",
                source_kind="standalone",
                source_title="Demo Tool",
                source_lecture_number=None,
                subjects=("testing",),
                runtime="static",
                href="tools/demo/",
            ),
        )
        tool_dir = self.tools_dir / "demo"
        tool_dir.mkdir(parents=True)
        (tool_dir / "index.qmd").write_text("# Demo\n", encoding="utf-8")
        destination = self.site_root / "generated" / "gallery.json"
        gallery.write_gallery_json(entries, destination, site_root=self.site_root)
        loaded = gallery.load_gallery_json(destination)
        self.assertEqual(loaded[0].id, "demo")
        payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["entries"]), 1)


class LiveRepositoryGalleryTest(unittest.TestCase):
    def test_repository_gallery_entrypoints_exist(self) -> None:
        site_root = content_model.SITE_ROOT
        gallery_path = site_root / "generated" / "gallery.json"
        if not gallery_path.exists():
            self.skipTest("generated/gallery.json not built; run build_interactives.py first")
        entries = gallery.load_gallery_json(gallery_path)
        gallery.validate_entrypoints_exist(entries, site_root)

    def test_built_site_contains_gallery_hrefs(self) -> None:
        site_root = content_model.SITE_ROOT
        built_site = site_root / "_site"
        gallery_path = site_root / "generated" / "gallery.json"
        if not built_site.is_dir() or not gallery_path.exists():
            self.skipTest("_site or gallery.json not available")
        entries = gallery.load_gallery_json(gallery_path)
        missing = [
            entry.href
            for entry in entries
            if not (built_site / entry.href.strip("/") / "index.html").exists()
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
