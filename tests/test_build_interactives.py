import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_interactives.py"
SPEC = importlib.util.spec_from_file_location("build_interactives", SCRIPT_PATH)
build_interactives = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = build_interactives
SPEC.loader.exec_module(build_interactives)


class BuildInteractivesTest(unittest.TestCase):
    def test_discovers_and_deduplicates_privacy_plot_embed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lecture = root / "lectures" / "03-test"
            lecture.mkdir(parents=True)
            code = (
                "PrivacyPlot(distribution_types=[norm, laplace], "
                "sensitivity=1, std=1.5).embed(mode='deck')"
            )
            (lecture / "slides.qmd").write_text(
                f"```{{python}}\n{code}\n```\n",
                encoding="utf-8",
            )
            (lecture / "learn.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {"cell_type": "code", "source": [code], "outputs": []}
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )

            uses = build_interactives.discover_interactives(root)

            self.assertEqual(len(uses), 1)
            self.assertEqual(uses[0].spec.preferred_backend, "wasm-marimo")
            self.assertIn("privacy-plot-norm-laplace-", uses[0].spec.artifact_name)

    def test_builds_importable_pure_python_wheel(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            wheel = build_interactives.build_libdpy_wheel(Path(temporary_directory))
            with zipfile.ZipFile(wheel) as archive:
                names = set(archive.namelist())

            self.assertIn("libdpy/__init__.py", names)
            self.assertIn("libdpy/visualization/interactive.py", names)
            self.assertIn("plotly/validators/_validators.json", names)
            self.assertIn("_plotly_utils/importers.py", names)
            self.assertTrue(any(name.endswith(".dist-info/RECORD") for name in names))


if __name__ == "__main__":
    unittest.main()
