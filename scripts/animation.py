"""Combine a sequence of matplotlib figures into a playable animation artifact.

Build tooling only — this module is imported by ``scripts/build_animations.py`` during the
site render, never by course content. It turns "a function that returns a sequence of plots"
into either a self-contained interactive **player** (matplotlib's ``to_jshtml`` — Prev/Next
stepping plus Play at a fixed frame rate) or a flat **gif/mp4** file.

The player is plain HTML + inline base64 PNG frames (no WASM, no server), so it embeds in a
blog post or a RevealJS slide via a simple ``<iframe>``. Its controls are on-screen buttons,
so they never collide with RevealJS arrow-key slide navigation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Union

import numpy as np
from matplotlib import rc_context
from matplotlib.animation import ArtistAnimation, FuncAnimation, PillowWriter
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

__all__ = ["PlotSequence"]

Frames = Union[int, Sequence[object]]

# matplotlib silently drops embedded frames once the encoded animation exceeds
# ``animation.embed_limit`` (default 20 MB). Presentation clips of a few dozen modest frames
# sit well under this; raise the ceiling so a slightly heavier clip renders in full rather
# than truncating without warning.
_DEFAULT_EMBED_LIMIT_MB = 64.0

_STANDALONE_TEMPLATE = (
    "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<style>html,body{{margin:0;padding:0;background:transparent}}"
    ".animation{{margin:0 auto;width:fit-content;max-width:100%}}"
    # The jshtml frame <img> has no intrinsic responsive sizing: at its natural pixel size it
    # overflows a narrower iframe and pushes the control bar out of view. Scale it to the iframe
    # width so the controls stay visible (the embed then auto-sizes the iframe to fit).
    ".animation img{{max-width:100%;height:auto;display:block}}</style></head>"
    "<body>{body}</body></html>\n"
)


def _check_fps(fps: float) -> None:
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps!r}")


def _rasterise(figure: Figure) -> np.ndarray:
    """Render a figure to an RGBA array and close it (so nothing lingers in pyplot)."""
    import matplotlib.pyplot as plt

    figure.canvas.draw()
    array = np.asarray(figure.canvas.buffer_rgba())
    plt.close(figure)
    return array


class PlotSequence:
    """A built matplotlib animation ready to emit as a player (HTML) or a gif/mp4 file."""

    def __init__(
        self,
        anim: FuncAnimation | ArtistAnimation,
        fig: Figure,
        *,
        fps: float,
        loop: bool = False,
        embed_limit_mb: float = _DEFAULT_EMBED_LIMIT_MB,
    ) -> None:
        _check_fps(fps)
        self._anim = anim
        self._fig = fig
        self.fps = float(fps)
        self.loop = bool(loop)
        self.embed_limit_mb = float(embed_limit_mb)
        self._html_cache: str | None = None

    # -- Construction ---------------------------------------------------------------

    @classmethod
    def from_figure_list(
        cls,
        figures: Iterable[Figure],
        *,
        fps: float = 8.0,
        loop: bool = False,
        embed_limit_mb: float = _DEFAULT_EMBED_LIMIT_MB,
    ) -> "PlotSequence":
        """Build from an already-materialised sequence of Figures (one per frame).

        This is the ``frames()`` sidecar contract: the author's function returns a list of
        Figures and they are chained into one animation. Every Figure must rasterise to the
        same pixel size (consistent ``figsize`` and ``dpi``); each is closed after rasterising.
        """
        _check_fps(fps)
        rasters: list[np.ndarray] = []
        size: tuple[int, int] | None = None
        dpi = 100.0
        for index, figure in enumerate(figures):
            if not isinstance(figure, Figure):
                raise TypeError(
                    f"frame {index} is {type(figure)!r}, expected a matplotlib Figure"
                )
            if size is None:
                dpi = float(figure.get_dpi())
            array = _rasterise(figure)
            this = (array.shape[1], array.shape[0])
            if size is None:
                size = this
            elif this != size:
                raise ValueError(
                    f"every frame must rasterise to the same pixel size; frame {index} is "
                    f"{this[0]}x{this[1]} but the first is {size[0]}x{size[1]}. "
                    "Use a consistent figsize and dpi."
                )
            rasters.append(array)
        if size is None:
            raise ValueError("frames sequence must not be empty")
        return cls._from_rasters(rasters, size, dpi, fps=fps, loop=loop, embed_limit_mb=embed_limit_mb)

    @classmethod
    def from_figures(
        cls,
        make_figure: Callable[[object], Figure],
        frames: Frames,
        *,
        fps: float = 8.0,
        loop: bool = False,
        embed_limit_mb: float = _DEFAULT_EMBED_LIMIT_MB,
    ) -> "PlotSequence":
        """Build by calling ``make_figure(key)`` once per frame (streaming form)."""
        keys = list(range(frames)) if isinstance(frames, int) else list(frames)
        if not keys:
            raise ValueError("frames must be a positive int or a non-empty sequence")
        return cls.from_figure_list(
            (make_figure(key) for key in keys),
            fps=fps,
            loop=loop,
            embed_limit_mb=embed_limit_mb,
        )

    @classmethod
    def from_draw(
        cls,
        draw: Callable[[Figure, object], object],
        frames: Frames,
        *,
        fps: float = 8.0,
        figsize: tuple[float, float] = (6.0, 4.0),
        dpi: int = 100,
        clear: bool = True,
        loop: bool = False,
        embed_limit_mb: float = _DEFAULT_EMBED_LIMIT_MB,
    ) -> "PlotSequence":
        """Build by redrawing one reused Figure per frame via ``draw(fig, key)``."""
        _check_fps(fps)
        keys = list(range(frames)) if isinstance(frames, int) else list(frames)
        if not keys:
            raise ValueError("frames must be a positive int or a non-empty sequence")
        fig = Figure(figsize=figsize, dpi=dpi)
        FigureCanvasAgg(fig)

        def _render(key: object) -> tuple:
            if clear:
                fig.clear()
            draw(fig, key)
            return ()

        anim = FuncAnimation(
            fig, _render, frames=keys, interval=1000.0 / fps, blit=False, repeat=loop
        )
        return cls(anim, fig, fps=fps, loop=loop, embed_limit_mb=embed_limit_mb)

    @classmethod
    def _from_rasters(
        cls,
        rasters: list[np.ndarray],
        size: tuple[int, int],
        dpi: float,
        *,
        fps: float,
        loop: bool,
        embed_limit_mb: float,
    ) -> "PlotSequence":
        width, height = size
        host = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        FigureCanvasAgg(host)
        ax = host.add_axes((0.0, 0.0, 1.0, 1.0))
        ax.set_axis_off()
        artists = [[ax.imshow(array, animated=True)] for array in rasters]
        anim = ArtistAnimation(host, artists, interval=1000.0 / fps, blit=False, repeat=loop)
        return cls(anim, host, fps=fps, loop=loop, embed_limit_mb=embed_limit_mb)

    # -- Output ---------------------------------------------------------------------

    def to_jshtml(self) -> str:
        """Return the self-contained player as an HTML *fragment* (frames inlined)."""
        if self._html_cache is None:
            default_mode = "loop" if self.loop else "once"
            with rc_context({"animation.embed_limit": self.embed_limit_mb}):
                self._html_cache = self._anim.to_jshtml(fps=self.fps, default_mode=default_mode)
        return self._html_cache

    def to_standalone_html(self) -> str:
        """Return a full HTML document wrapping the player (for an ``<iframe>`` src)."""
        return _STANDALONE_TEMPLATE.format(body=self.to_jshtml())

    def save(self, path: str | Path, *, dpi: int | None = None) -> Path:
        """Write the animation to ``.gif`` (Pillow) or ``.mp4``/``.webm`` (ffmpeg)."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".gif":
            writer = PillowWriter(fps=self.fps)
        elif suffix in {".mp4", ".webm", ".mov", ".m4v"}:
            from matplotlib.animation import FFMpegWriter

            if not FFMpegWriter.isAvailable():
                raise RuntimeError(
                    f"saving {suffix} requires a system ffmpeg on PATH; install ffmpeg or "
                    "export a .gif instead."
                )
            writer = FFMpegWriter(fps=self.fps)
        else:
            raise ValueError(f"unsupported output extension {suffix!r}; use .gif, .mp4, or .webm")
        save_dpi = dpi if dpi is not None else self._fig.get_dpi()
        path.parent.mkdir(parents=True, exist_ok=True)
        with rc_context({"savefig.bbox": None}):  # bbox='tight' breaks animation writers
            self._anim.save(str(path), writer=writer, dpi=save_dpi)
        return path
