import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.animation import PlotSequence  # noqa: E402


def _count_frames(html: str) -> int:
    return len(re.findall(r"data:image/png;base64,", html))


def _make_fig(i: int):
    fig = plt.figure(figsize=(4, 3), dpi=80)
    fig.add_subplot().plot([0, 1, 2], [0, i, 0])
    return fig


class FromFigureListTest(unittest.TestCase):
    def test_player_has_one_frame_per_figure_and_closes_sources(self) -> None:
        plt.close("all")
        seq = PlotSequence.from_figure_list((_make_fig(i) for i in range(4)), fps=6)
        html = seq.to_jshtml()
        self.assertEqual(_count_frames(html), 4)
        self.assertIn("anim-buttons", html)
        self.assertEqual(plt.get_fignums(), [])  # every source figure closed

    def test_standalone_html_is_a_full_document(self) -> None:
        seq = PlotSequence.from_figure_list([_make_fig(0), _make_fig(1)], fps=6)
        doc = seq.to_standalone_html()
        self.assertTrue(doc.lstrip().startswith("<!doctype html>"))
        self.assertIn("</html>", doc)
        self.assertEqual(_count_frames(doc), 2)

    def test_inconsistent_sizes_rejected(self) -> None:
        plt.close("all")

        def figs():
            yield _make_fig(0)
            big = plt.figure(figsize=(5, 3), dpi=80)
            big.add_subplot().plot([0, 1], [0, 1])
            yield big

        with self.assertRaises(ValueError):
            PlotSequence.from_figure_list(figs(), fps=6)
        self.assertEqual(plt.get_fignums(), [])

    def test_empty_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PlotSequence.from_figure_list([], fps=6)


class FromFiguresAndDrawTest(unittest.TestCase):
    def test_from_figures_streaming(self) -> None:
        plt.close("all")
        seq = PlotSequence.from_figures(_make_fig, 5, fps=10)
        self.assertEqual(_count_frames(seq.to_jshtml()), 5)
        self.assertEqual(plt.get_fignums(), [])

    def test_from_draw(self) -> None:
        plt.close("all")
        seq = PlotSequence.from_draw(
            lambda fig, i: fig.add_subplot().plot([0, 1], [0, i]), frames=3, fps=8
        )
        self.assertEqual(_count_frames(seq.to_jshtml()), 3)
        self.assertEqual(plt.get_fignums(), [])

    def test_fps_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            PlotSequence.from_figures(_make_fig, 2, fps=0)


class SaveTest(unittest.TestCase):
    def _seq(self) -> PlotSequence:
        return PlotSequence.from_figures(_make_fig, 3, fps=5)

    def test_save_gif_writes_nonempty_file(self) -> None:
        with TemporaryDirectory() as tmp:
            out = self._seq().save(Path(tmp) / "clip.gif")
            self.assertTrue(out.exists() and out.stat().st_size > 0)

    def test_save_rejects_unknown_extension(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._seq().save(Path(tmp) / "clip.bogus")


if __name__ == "__main__":
    unittest.main()
