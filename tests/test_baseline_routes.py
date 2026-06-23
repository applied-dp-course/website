"""Validate the baseline route fixture against the live catalog."""

from __future__ import annotations

import importlib.util
import json
import sys
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

BASELINE_PATH = SITE_ROOT / "dev" / "plan" / "baseline-routes.json"


class BaselineRoutesTest(unittest.TestCase):
    def test_baseline_fixture_exists(self) -> None:
        self.assertTrue(BASELINE_PATH.is_file())

    def test_baseline_matches_current_required_routes(self) -> None:
        payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        catalog = content_model.load_catalog()
        routes = check_site.required_routes(catalog)
        self.assertEqual(payload["page_routes"], list(check_site.REQUIRED_PAGE_ROUTES))
        self.assertEqual(set(payload["required_routes"]), set(routes))


if __name__ == "__main__":
    unittest.main()
