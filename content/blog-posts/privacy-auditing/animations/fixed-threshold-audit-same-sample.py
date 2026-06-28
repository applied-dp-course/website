"""Fixed-threshold audit on the same sample as the empirical ROC step.

Build sidecar: ``frames()`` runs during ``quarto render`` and writes
``_generated/animations/blog-posts/privacy-auditing/fixed-threshold-audit-same-sample.html``,
which the post embeds via ``animation_player_iframe``. The threshold is frozen from the
seeded empirical ROC; experiments arrive in balanced random order on the same finite sample.
"""

import numpy as np

from libdpy.assignment_specific.privacy_auditing.animations import (
    fixed_threshold_audit_frames_from_samples,
)
from libdpy.assignment_specific.privacy_auditing.lecture_figures import (
    make_two_logistic_samplers,
)
from libdpy.assignment_specific.privacy_auditing.utils import (
    selected_threshold_from_empirical_roc,
)

FPS = 24
OUTPUTS = ("player",)
LOOP = False

_SEED_EMPIRICAL_ROC = 4
_N_PER_CLASS = 500
_DELTA = 1e-2
_N_FRAMES = 200

_sampler_neg, _sampler_pos = make_two_logistic_samplers(scale1=1.0, scale2=0.4)
_rng = np.random.default_rng(_SEED_EMPIRICAL_ROC)
_samples_neg = _sampler_neg(n=_N_PER_CLASS, rng=_rng)
_samples_pos = _sampler_pos(n=_N_PER_CLASS, rng=_rng)
_tau_star, _, _ = selected_threshold_from_empirical_roc(
    _samples_neg,
    _samples_pos,
    _DELTA,
)


def frames():
    """Yield fixed-threshold audit frames on the empirical-ROC sample."""

    yield from fixed_threshold_audit_frames_from_samples(
        _samples_neg,
        _samples_pos,
        _tau_star,
        seed=_SEED_EMPIRICAL_ROC,
        delta=_DELTA,
        n_frames=_N_FRAMES,
    )
