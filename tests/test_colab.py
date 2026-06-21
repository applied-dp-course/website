import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "colab.py"
SPEC = importlib.util.spec_from_file_location("colab", SCRIPT_PATH)
colab = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = colab
SPEC.loader.exec_module(colab)


class ColabUrlTest(unittest.TestCase):
    def test_notebook_url_uses_github_blob_path(self) -> None:
        url = colab.notebook_url(
            owner="applied-dp-course",
            name="website",
            branch="main",
            repo_relative_path="content/assignments/hypothesis-testing-hw/assignment.ipynb",
        )
        self.assertEqual(
            url,
            "https://colab.research.google.com/github/applied-dp-course/website/blob/main/"
            "content/assignments/hypothesis-testing-hw/assignment.ipynb",
        )

    def test_notebook_url_encodes_spaces(self) -> None:
        url = colab.notebook_url(
            owner="owner",
            name="repo",
            branch="main",
            repo_relative_path="content/lectures/my topic/learn.ipynb",
        )
        self.assertIn("my%20topic", url)

    def test_badge_markdown_uses_standard_asset(self) -> None:
        badge = colab.badge_markdown("https://example.com/notebook")
        self.assertIn("colab.research.google.com/assets/colab-badge.svg", badge)
        self.assertIn("](https://example.com/notebook)", badge)

    def test_badge_for_notebook_disabled_returns_empty_string(self) -> None:
        badge = colab.badge_for_notebook(
            enabled=False,
            owner="owner",
            name="repo",
            branch="main",
            repo_relative_path="content/assignments/hw/assignment.ipynb",
        )
        self.assertEqual(badge, "")

    def test_badge_for_notebook_enabled_returns_markdown_link(self) -> None:
        badge = colab.badge_for_notebook(
            enabled=True,
            owner="applied-dp-course",
            name="website",
            branch="main",
            repo_relative_path="content/lectures/03-hypothesis_testing/learn.ipynb",
        )
        self.assertIn("Open in Colab", badge)
        self.assertIn(
            "content/lectures/03-hypothesis_testing/learn.ipynb",
            badge,
        )


if __name__ == "__main__":
    unittest.main()
