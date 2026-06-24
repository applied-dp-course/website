import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from scripts import build_animations

_SIDECAR = dedent(
    '''
    import matplotlib.pyplot as plt

    FPS = 6
    OUTPUTS = {outputs!r}

    def frames():
        for i in range(3):
            fig, ax = plt.subplots(figsize=(3, 2), dpi=80)
            ax.plot([0, 1], [0, i])
            yield fig
    '''
)


class BuildAnimationsTest(unittest.TestCase):
    def _build(self, outputs, tmp):
        """Create a sidecar under a temp content tree and build it; return the item dir."""
        root = Path(tmp)
        sidecar = root / "content" / "blog-posts" / "demo" / "animations" / "wave.py"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(_SIDECAR.format(outputs=tuple(outputs)))

        # Redirect the hook's roots at the temp tree.
        self.enterContext_patch(build_animations, "SITE_ROOT", root)
        self.enterContext_patch(build_animations, "CONTENT_ROOT", root / "content")
        self.enterContext_patch(
            build_animations, "GENERATED_ROOT", root / "_generated" / "animations"
        )

        found = build_animations.discover_sidecars(root / "content")
        self.assertEqual(found, [sidecar])
        build_animations.build_sidecar(sidecar)
        return root / "_generated" / "animations" / "blog-posts" / "demo"

    def enterContext_patch(self, obj, attr, value):
        original = getattr(obj, attr)
        setattr(obj, attr, value)
        self.addCleanup(setattr, obj, attr, original)

    def test_player_only(self) -> None:
        with TemporaryDirectory() as tmp:
            out = self._build(("player",), tmp)
            self.assertTrue((out / "wave.html").exists())
            self.assertFalse((out / "wave.gif").exists())
            html = (out / "wave.html").read_text()
            self.assertTrue(html.lstrip().startswith("<!doctype html>"))
            self.assertEqual(html.count("data:image/png;base64,"), 3)

    def test_gif_only_does_not_emit_player(self) -> None:
        with TemporaryDirectory() as tmp:
            out = self._build(("gif",), tmp)
            self.assertTrue((out / "wave.gif").exists())
            self.assertGreater((out / "wave.gif").stat().st_size, 0)
            self.assertFalse((out / "wave.html").exists())

    def test_both_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            out = self._build(("player", "gif"), tmp)
            self.assertTrue((out / "wave.html").exists())
            self.assertTrue((out / "wave.gif").exists())

    def test_unknown_output_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._build(("bogus",), tmp)


if __name__ == "__main__":
    unittest.main()
