import builtins
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from scripts import assert_private_content, colab_setup, content_model


SITE_ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_NOTEBOOK = (
    SITE_ROOT
    / "content"
    / "class-assignments"
    / "hypothesis-testing"
    / "assignment.ipynb"
)


class AssignmentColabSetupTest(unittest.TestCase):
    def test_setup_cell_uses_git_install_spec(self) -> None:
        notebook = colab_setup.load_notebook(ASSIGNMENT_NOTEBOOK)
        source = colab_setup.setup_cell_source(notebook)
        self.assertIn(colab_setup.LIBDPY_GIT_INSTALL, source)

    def test_setup_cell_calls_pip_when_libdpy_missing(self) -> None:
        notebook = colab_setup.load_notebook(ASSIGNMENT_NOTEBOOK)
        script = colab_setup.colab_setup_script(colab_setup.setup_cell_source(notebook))
        attempts = {"count": 0}
        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "libdpy":
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise ImportError("clean runtime")
                module = types.ModuleType("libdpy")
                sys.modules["libdpy"] = module
                return module
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            with mock.patch("subprocess.check_call") as check_call:
                exec(compile(script, "<setup>", "exec"), {})
        check_call.assert_called_once()


class PrivateSolutionPublicationTest(unittest.TestCase):
    def test_quarto_excludes_both_solution_collections(self) -> None:
        config = (SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn("!content/class-assignments/**/solution.ipynb", config)
        self.assertIn("!content/home-assignments/**/solution.ipynb", config)

    def test_solution_cannot_be_published_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            item = root / "bad-homework"
            item.mkdir()
            (item / "solution.ipynb").write_text("{}", encoding="utf-8")
            (item / "manifest.yml").write_text(
                "title: Bad\nentrypoint: solution.ipynb\nstatus: draft\n",
                encoding="utf-8",
            )
            with self.assertRaises(content_model.ContentValidationError):
                content_model.discover_items(root, "home-assignment", ".ipynb")

    def test_built_site_contains_no_solution_artifacts(self) -> None:
        site_root = SITE_ROOT / "_site"
        if not site_root.is_dir():
            self.skipTest("_site not built")
        self.assertEqual(assert_private_content.check_site(site_root), [])


if __name__ == "__main__":
    unittest.main()
