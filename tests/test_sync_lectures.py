import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_lectures.py"
SPEC = importlib.util.spec_from_file_location("sync_lectures", SCRIPT_PATH)
sync_lectures = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = sync_lectures
SPEC.loader.exec_module(sync_lectures)


class SyncLecturesTest(unittest.TestCase):
    def test_two_uploaded_sources_create_all_registration_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            lecture_dir = site_root / "lectures" / "04-new-topic"
            lecture_dir.mkdir(parents=True)
            (lecture_dir / "deck-source.qmd").write_text(
                '---\ntitle: "New Topic"\nformat: revealjs\n---\n',
                encoding="utf-8",
            )
            (lecture_dir / "study-source.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )
            marker_section = (
                f"{sync_lectures.BEGIN_MARKER}\nold\n{sync_lectures.END_MARKER}\n"
            )
            (site_root / "lectures.qmd").write_text(marker_section, encoding="utf-8")
            (site_root / "schedule.qmd").write_text(marker_section, encoding="utf-8")

            original_site_root = sync_lectures.SITE_ROOT
            original_lectures_dir = sync_lectures.LECTURES_DIR
            try:
                sync_lectures.SITE_ROOT = site_root
                sync_lectures.LECTURES_DIR = site_root / "lectures"
                sync_lectures.main()
            finally:
                sync_lectures.SITE_ROOT = original_site_root
                sync_lectures.LECTURES_DIR = original_lectures_dir

            self.assertTrue((lecture_dir / "slides.qmd").exists())
            self.assertTrue((lecture_dir / "learn.ipynb").exists())
            self.assertTrue((lecture_dir / "manifest.yml").exists())
            self.assertIn(
                "04 · New Topic",
                (site_root / "lectures.qmd").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "| 04 | New Topic | planned |",
                (site_root / "schedule.qmd").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
