"""Threshold-sweep animation for the privacy-auditing post.

Build sidecar (see scripts/build_animations.py): `frames()` runs during `quarto render` and
its output is written to `_generated/animations/blog-posts/privacy-auditing/threshold-sweep.html`,
which the post embeds via an <iframe>. Sweeping the decision threshold tau traces the ROC curve.

This module imports nothing from the build — just numpy/scipy/matplotlib.
"""

import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats

FPS = 12
OUTPUTS = ("player",)  # "player" -> interactive HTML; add "gif"/"mp4" for a flat file too

_neg = stats.laplace(0, 1)  # H0: target user absent
_pos = stats.laplace(1, 1)  # H1: target user present
_taus = np.linspace(-4, 5, 40)
_fpr = _neg.sf(_taus)  # FPR = P(X > tau) under H0
_tpr = _pos.sf(_taus)  # TPR = P(X > tau) under H1
_grid = np.linspace(-6, 7, 400)


def frames():
    """Yield one Figure per threshold value (the sequence of plots to chain).

    A generator keeps only one figure open at a time; returning a list works too for short
    clips, but holds every frame in memory at once.
    """
    for i, tau in enumerate(_taus):
        fig, (ax_pdf, ax_roc) = plt.subplots(1, 2, figsize=(9, 4), dpi=110)
        ax_pdf.plot(_grid, _neg.pdf(_grid), "C3", label="$H_0$ (out)")
        ax_pdf.plot(_grid, _pos.pdf(_grid), "C0", label="$H_1$ (in)")
        ax_pdf.axvline(tau, color="black", lw=1)
        ax_pdf.fill_between(_grid, _neg.pdf(_grid), where=_grid > tau, color="C3", alpha=0.2)
        ax_pdf.fill_between(_grid, _pos.pdf(_grid), where=_grid > tau, color="C0", alpha=0.2)
        ax_pdf.set_title(fr"Threshold $\tau = {tau:.2f}$")
        ax_pdf.set_xlabel("noisy released value")
        ax_pdf.legend(loc="upper right")
        ax_roc.plot(_fpr, _tpr, color="0.8")
        ax_roc.plot(_fpr[: i + 1], _tpr[: i + 1], color="C2", lw=2)
        ax_roc.scatter([_fpr[i]], [_tpr[i]], color="C2", zorder=3)
        ax_roc.plot([0, 1], [0, 1], "k--", lw=0.8)
        ax_roc.set_xlim(0, 1)
        ax_roc.set_ylim(0, 1)
        ax_roc.set_xlabel("FPR")
        ax_roc.set_ylabel("TPR")
        ax_roc.set_title("ROC curve")
        fig.tight_layout()
        yield fig
