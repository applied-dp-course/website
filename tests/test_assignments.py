import unittest

from scripts import content_model, sync_content


class AssignmentsPageTest(unittest.TestCase):
    def test_assignments_are_split_by_kind(self) -> None:
        catalog = content_model.load_catalog()
        rendered = sync_content.render_assignments_page(catalog)
        self.assertIn("## Class assignments", rendered)
        self.assertIn("Hypothesis Testing Assignment", rendered)
        self.assertIn("Week 2 (2026-10-27)", rendered)
        self.assertIn("## Home assignments", rendered)
        self.assertIn("No home assignments are published", rendered)

    def test_schedule_links_named_class_assignment(self) -> None:
        rendered = sync_content.render_schedule_page(content_model.load_catalog())
        self.assertIn("content/class-assignments/hypothesis-testing/assignment.ipynb", rendered)
        self.assertIn("colab.research.google.com", rendered)


if __name__ == "__main__":
    unittest.main()
