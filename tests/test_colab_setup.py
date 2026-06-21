import importlib.util
import builtins
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from shutil import which
from unittest import mock


SITE_ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_NOTEBOOK = (
    SITE_ROOT / "content" / "assignments" / "hypothesis-testing-hw" / "assignment.ipynb"
)

COLAB_SETUP_PATH = SITE_ROOT / "scripts" / "colab_setup.py"
SPEC = importlib.util.spec_from_file_location("colab_setup", COLAB_SETUP_PATH)
colab_setup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = colab_setup
SPEC.loader.exec_module(colab_setup)

ASSERT_PRIVATE_PATH = SITE_ROOT / "scripts" / "assert_private_content.py"
SPEC = importlib.util.spec_from_file_location("assert_private_content", ASSERT_PRIVATE_PATH)
assert_private_content = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = assert_private_content
SPEC.loader.exec_module(assert_private_content)


class AssignmentColabSetupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.notebook = colab_setup.load_notebook(ASSIGNMENT_NOTEBOOK)
        self.setup_source = colab_setup.setup_cell_source(self.notebook)

    def test_setup_cell_uses_git_install_spec(self) -> None:
        self.assertIn(colab_setup.LIBDPY_GIT_INSTALL, self.setup_source)

    def test_setup_cell_calls_pip_when_libdpy_missing(self) -> None:
        script = colab_setup.colab_setup_script(self.setup_source)
        import_attempts = {"count": 0}
        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "libdpy":
                import_attempts["count"] += 1
                if import_attempts["count"] == 1:
                    raise ImportError("simulated clean Colab runtime")
                module = types.ModuleType("libdpy")
                sys.modules["libdpy"] = module
                return module
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            with mock.patch("subprocess.check_call") as check_call:
                exec(compile(script, "<setup>", "exec"), {})

        self.assertEqual(import_attempts["count"], 2)
        check_call.assert_called_once()
        pip_command = check_call.call_args.args[0]
        self.assertEqual(pip_command[:4], [sys.executable, "-m", "pip", "install"])
        self.assertIn(colab_setup.LIBDPY_GIT_INSTALL, pip_command[5])

    def test_setup_cell_installs_libdpy_in_clean_venv(self) -> None:
        script = colab_setup.colab_setup_script(self.setup_source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            venv_dir = Path(temporary_directory) / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
            )
            python = venv_dir / "bin" / "python"
            completed = subprocess.run(
                [python, "-c", script + "\nimport sys\nassert 'libdpy' in sys.modules\n"],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if completed.returncode != 0:
                self.fail(
                    "clean-venv Colab setup failed:\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )


class PrivateSolutionPublicationTest(unittest.TestCase):
    def test_quarto_render_list_excludes_solution_notebooks(self) -> None:
        quarto_config = (SITE_ROOT / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn("!content/assignments/**/solution.ipynb", quarto_config)

    def test_manifest_cannot_declare_solution_notebook(self) -> None:
        content_model_path = SITE_ROOT / "scripts" / "content_model.py"
        spec = importlib.util.spec_from_file_location("content_model", content_model_path)
        content_model = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = content_model
        spec.loader.exec_module(content_model)

        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            assignments_dir = site_root / "content" / "assignments" / "bad-hw"
            lectures_dir = site_root / "content" / "lectures" / "03-hypothesis_testing"
            assignments_dir.mkdir(parents=True)
            lectures_dir.mkdir(parents=True)
            (lectures_dir / "learn.ipynb").write_text("{}", encoding="utf-8")
            (lectures_dir / "slides.qmd").write_text(
                '---\ntitle: "DP as Hypothesis Testing"\n---\n',
                encoding="utf-8",
            )
            (lectures_dir / "manifest.yml").write_text(
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
            (assignments_dir / "solution.ipynb").write_text("{}", encoding="utf-8")
            (assignments_dir / "manifest.yml").write_text(
                "\n".join(
                    [
                        "title: Bad Assignment",
                        "subjects:",
                        "  - testing",
                        "notebook: solution.ipynb",
                        "status: published",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(content_model.ContentValidationError) as context:
                content_model.discover_assignments(
                    site_root / "content" / "assignments",
                    lectures_dir=lectures_dir,
                )
            self.assertIn("solution.ipynb must not be declared", str(context.exception))

    def test_built_site_contains_no_solution_artifacts(self) -> None:
        site_root = SITE_ROOT / "_site"
        if not site_root.is_dir():
            self.skipTest("_site not built")
        published = assert_private_content.check_site(site_root)
        self.assertEqual(published, [])

    @unittest.skipUnless(which("quarto"), "quarto not installed")
    def test_quarto_does_not_render_solution_notebook(self) -> None:
        quarto = which("quarto")
        assert quarto is not None
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            assignments_dir = site_root / "content" / "assignments" / "probe-hw"
            assignments_dir.mkdir(parents=True)
            (assignments_dir / "assignment.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "markdown",
                                "metadata": {},
                                "source": ["# Public assignment\n"],
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )
            (assignments_dir / "solution.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "markdown",
                                "metadata": {},
                                "source": ["# PRIVATE SOLUTION\n"],
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )
            (site_root / "_quarto.yml").write_text(
                "\n".join(
                    [
                        "project:",
                        "  type: website",
                        "  output-dir: _site",
                        "  render:",
                        '    - "content/assignments/**/*.ipynb"',
                        '    - "!content/assignments/**/solution.ipynb"',
                        "format:",
                        "  html:",
                        "    theme: cosmo",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [str(quarto), "render", "--no-execute"],
                cwd=site_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"quarto render failed:\n{completed.stderr}",
            )

            built_site = site_root / "_site"
            self.assertTrue(
                (built_site / "content/assignments/probe-hw/assignment.html").exists()
            )
            self.assertFalse((built_site / "content/assignments/probe-hw/solution.html").exists())
            self.assertEqual(assert_private_content.check_site(built_site), [])


if __name__ == "__main__":
    unittest.main()
