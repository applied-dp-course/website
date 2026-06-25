"""Empirical-ROC accumulation animation for the privacy-auditing slide deck.

Build sidecar (see scripts/build_animations.py): `frames()` runs during `quarto render`
and its output is written to
`_generated/animations/lecture-presentations/privacy-auditing/empirical-roc.gif`, which
the deck embeds via an <img>. Frame *i* shows the empirical ROC built from the first *i*
sampled points per class, so the curve fills in as samples accumulate.

Per the lecture contract, the frame-generating logic lives in libdpy; this sidecar only
selects the mechanism + seed and hands the frames to the website's GIF converter. It
mirrors the post sidecar so the deck and the self-study notebook show the same animation.
"""

import numpy as np

from libdpy.assignment_specific.privacy_auditing.animations import (
    empirical_roc_accumulation_frames,
)
from libdpy.assignment_specific.privacy_auditing.lecture_figures import (
    make_two_logistic_samplers,
)

FPS = 24
OUTPUTS = ("gif",)  # one lightweight flat GIF; no heavy per-frame HTML player

_N_FRAMES = 200
_SEED_EMPIRICAL_ROC = 4
_sampler_neg, _sampler_pos = make_two_logistic_samplers(scale1=1.0, scale2=0.4)


def frames():
    """Yield the 200 empirical-ROC accumulation frames (one Figure per step)."""

    yield from empirical_roc_accumulation_frames(
        _sampler_neg,
        _sampler_pos,
        n_frames=_N_FRAMES,
        rng=np.random.default_rng(_SEED_EMPIRICAL_ROC),
    )
