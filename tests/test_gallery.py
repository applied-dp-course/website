import unittest

from scripts import content_model, gallery


class GalleryBuildTest(unittest.TestCase):
    def test_live_gallery_uses_apps_outside_content(self) -> None:
        entries = gallery.build_gallery_entries(content_model.load_catalog())
        hrefs = {entry.href for entry in entries}
        self.assertIn(
            "_generated/apps/lecture-presentations/reconstruction-attacks/reconstruction-2d-slab/",
            hrefs,
        )
        self.assertIn(
            "_generated/apps/lecture-presentations/hypothesis-testing/privacy-plot-norm-6197737a49/",
            hrefs,
        )
        self.assertIn(
            "content/tools/privacy-tradeoff-explorer/",
            hrefs,
        )
        self.assertFalse(
            any(href.startswith("content/lecture-presentations/") for href in hrefs)
        )

    def test_gallery_ids_are_unique(self) -> None:
        entries = gallery.build_gallery_entries(content_model.load_catalog())
        gallery.validate_unique_ids(entries)
        self.assertEqual(len(entries), len({entry.id for entry in entries}))

    def test_authored_app_entrypoints_exist(self) -> None:
        entries = tuple(
            entry
            for entry in gallery.build_gallery_entries(content_model.load_catalog())
            if entry.runtime in {"external-app", "browser-native"} or entry.source_kind == "standalone"
        )
        gallery.validate_entrypoints_exist(entries, content_model.SITE_ROOT)


if __name__ == "__main__":
    unittest.main()
