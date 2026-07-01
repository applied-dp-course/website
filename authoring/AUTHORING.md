# Authoring guide

Authors edit two places:

- `pages/` for main site pages such as Home, Schedule, Syllabus, Blog listing, and About.
- `content/` for reusable course material and other authored site content.

The build may update marked generated sections inside `pages/`. It must never write into
`content/`.

## Content collections

| Collection | Source | Purpose |
|---|---|---|
| `content/lecture-presentations/<name>/` | `presentation.qmd` | RevealJS lecture deck |
| `content/blog-posts/<name>/` | `post.ipynb` | Self-learning blog post (course catalog) |
| `content/site-posts/<name>/` | `index.qmd` | Editorial blog post (listed on `pages/blog.qmd`) |
| `content/tools/<name>/` | `index.qmd` | Standalone interactive tool |
| `content/class-assignments/<name>/` | `assignment.ipynb` | In-class assignment |
| `content/home-assignments/<name>/` | `assignment.ipynb` | Home assignment |

`<name>` is a stable lowercase kebab-case identifier such as `privacy-auditing`. Do not prefix
names with lecture or week numbers. Each directory also contains a hand-written `manifest.yml`.

Generated HTML, notebook caches, rendered figures, WASM apps, and generated manifests do not
belong under `content/`. Generated interactives are written to `_generated/apps/`. Quarto may write
execution results back into notebooks while rendering; the first post-render hook removes them
immediately.

## Add content

Lecture presentation:

```bash
cp -R authoring/templates/lecture-presentation \
  content/lecture-presentations/mechanisms
```

Blog post:

```bash
cp -R authoring/templates/blog-post content/blog-posts/mechanisms
```

Class assignment:

```bash
cp -R authoring/templates/class-assignment \
  content/class-assignments/mechanisms
```

For a home assignment, use the class-assignment template but place it under
`content/home-assignments/`.

Standalone tool:

```bash
cp -R authoring/templates/tool content/tools/my-tool
```

Edit the copied `manifest.yml` and source file. Set `gallery: true` in the tool manifest to list
it on **Tools**. The manifest `entrypoint` must be QMD for lecture presentations, tools, and site
posts, and a notebook for the assignment and blog-post collections.

### Content that depends on a new `libdpy` API

The site installs `libdpy` **unpinned from `pub_lib`**, and `./dev/tools/render.sh` re-syncs it
before rendering. So content using **any** library API not yet on `pub_lib` — a new function, a new
keyword argument, or a newly registered interactive — will fail to build until that API is
**released to `pub_lib` first**. Release it (see
`code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md`), then render. Do **not** `pip install -e` a local
libdpy into `.venv`: `sync_libdpy.sh` reverts it on the next render. For a deliberate pre-release
local check only, use `LIBDPY_SYNC=0 ./dev/tools/render.sh`.

The trigger is not only new kwargs: **adding a new class to `EMBED_CONSTRUCTOR_NAMES`**
(`libdpy.visualization.registry`) is itself a library change that needs a version bump and a
`pub_lib` release before its `.embed()` calls resolve on the site.

## Developing a lecture (end to end)

A lecture ships two authored artifacts — `blog-posts/<slug>/post.ipynb` (self-learning) and
`lecture-presentations/<slug>/presentation.qmd` (deck) — both derived from the private dev notebook
`code_base_dev/lectures/lecture_<topic>.ipynb` and importing the same `libdpy` helpers. The dev
notebook is the permanent source and is **never deleted**; the two website copies are kept in
parallel (drift accepted — the blog-post smoke route is the tripwire).

**Preconditions.** The tree is green (content validation + the plot-inventory scan pass on `main`),
and every `libdpy` API the content uses is **already released to `pub_lib`** — see *Content that
depends on a new `libdpy` API* above, and `code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md` for how a
release works (that is a code_base_dev step, not a website one).

**Steps.** Author both artifacts (*Add content*) → use `.embed()` for interactives (*Plotting
policy*) → validate with `./dev/tools/render.sh` then `./.venv/bin/python tests/run_smoke_tests.py`
(*Validation*), confirming `_generated/apps/**/<slug>/…` WASM and green smoke for both routes → add
the slug to `content/offerings/<term>/schedule.csv` and set both manifests to `published`.

**Deck vs blog interactives.** The two artifacts need not carry the same interactives. The
convention (applied to private-estimation): the **deck** uses static `make_*_figure()` factories for
speed and print-safety, while the **blog post** carries the interactive `.embed()` explorers — not
every interactive in the dev notebook must appear in both.

## Configure an offering

Copy `authoring/templates/offering` to `content/offerings/<term>/`. The schedule header is:

```csv
week,date,topic,blog_post,lecture_presentation,class_assignment,home_assignment,notes
```

Each content cell contains an item name, for example:

```csv
1,2027-01-19,Mechanisms,mechanisms,mechanisms,,,
```

Blank cells are valid. Set `current_offering` in `content/course.yml` to switch the live term.

## Animated plot sequences (player / gif / video)

Animations are produced by the **build**, not by content. You write a function that returns a
sequence of plots in a *sidecar* module; the pre-render hook `scripts/build_animations.py` combines
the frames while the site renders, and your page embeds the generated artifact. The notebook/slide
imports nothing, so it stays Colab-safe. Full walkthrough:
`authoring/examples/animated-plot-sequence/index.qmd`.

**1. Sidecar** — `content/<collection>/<item>/animations/<name>.py` (numpy/matplotlib only):

```python
import numpy as np, matplotlib.pyplot as plt

FPS = 10
OUTPUTS = ("player",)        # any of: "player", "gif", "mp4"  -- the selection knob

def frames():                # a generator keeps one figure open at a time
    x = np.linspace(0, 2 * np.pi, 200)
    for i in range(20):
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(x, np.sin(x - 0.3 * i)); ax.set_ylim(-1.1, 1.1)
        yield fig
```

(Alternatively define `make_figure(i)` plus a module-level `FRAMES` count.)

**2. `OUTPUTS`** selects what the build writes to
`_generated/animations/<collection>/<item>/<name>.<ext>`: `player` → an interactive `.html`
(Prev/Next stepping + Play at the fixed `FPS`); `gif`/`mp4` → a flat file (mp4 needs system ffmpeg).
List several to emit more than one.

**3. Embed the artifact** (use ``libdpy.visualization.animation_embed`` so content does not
hand-write ``_generated/animations/...`` paths). Player — in a post or RevealJS slide
(controls are mouse-driven, so they don't clash with slide arrow keys):

```{python}
#| echo: false
#| output: asis
from libdpy.visualization.animation_embed import animation_player_iframe
print(animation_player_iframe("blog-posts", "my-post", "wave"))
```

Flat gif in a post or slide:

```{python}
#| echo: false
#| output: asis
from libdpy.visualization.animation_embed import animation_markdown_image
print(animation_markdown_image("blog-posts", "my-post", "wave", alt="Wave"))
```

Notes:

- Build/preview just the animations with `./.venv/bin/python scripts/build_animations.py`
  (`--discover-only` to list sidecars). `_generated/` is git-ignored and rebuilt each render.
- Stepping is via Prev/Next buttons; the frame rate is fixed at build time (`FPS`) — no scrubber or
  runtime speed slider.
- Every frame must rasterise to the **same pixel size** (consistent `figsize`/`dpi`). Frames are
  inlined as base64 PNGs, so keep `frames × dpi` modest.
- Live example: `content/blog-posts/privacy-auditing/animations/empirical-roc.py`.

## Validation

```bash
./.venv/bin/python scripts/content_model.py
./.venv/bin/python -m pytest tests -q
./dev/tools/render.sh
./.venv/bin/python tests/run_smoke_tests.py
```

Validation rejects numbered content names, missing entrypoints, wrong source types, offering
references that do not match an authored content name, and **notebooks whose `kernelspec.name` is not
`python3`** (CI rejects e.g. `libdpy-base-local` — reset the kernel to `python3` before committing).
`run_smoke_tests.py` is the **required final gate for any content with interactives** — it opens the
rendered WASM apps in a headless browser and must pass before the content is considered done.

**Incremental (single-lecture) loop.** The four commands above are the full "done" gate; while
iterating on one lecture, a faster loop avoids the site-wide render + smoke:

```bash
./.venv/bin/python -m pytest tests/test_plot_inventory_scan.py -k pre_render
./.venv/bin/python scripts/build_interactives.py                 # rebuild WASM apps only
quarto render content/blog-posts/<slug>/post.ipynb               # render one notebook
./.venv/bin/python tests/run_smoke_tests.py --slug <slug>        # scoped full-page smoke
```

The scoped smoke command runs only the matching full-page WASM routes and skips the
site-wide per-app loop (each app can take up to five minutes locally). Use
`tests/smoke_full_page_wasm.py` against a served URL for an even lighter check while
iterating; pass `--include-per-app` to `run_smoke_tests.py` if you also need the
standalone per-app pass.

A full `./dev/tools/render.sh` is still required before "done" when artifact names change, animation
sidecars are added/changed, or offering/page sync is affected.

Private `solution.ipynb` files under class or home assignments are ignored and blocked from the
rendered site.

## Plotting policy

Course visuals use three author-facing paths.

**Static figures** — prefer library `make_*_figure(...)` factories that return a Matplotlib or
Plotly figure without calling `show()`. In notebooks and QMD, let Jupyter/Quarto capture the
returned figure.

**Interactives** — use plot wrapper classes with `Plot(...).show()` in live notebooks/Colab and
`Plot(...).embed(mode="page"|"deck")` in website sources. The build discovers registered
constructors and exports marimo WASM apps to `_generated/apps/`. Colab falls back to live widgets
inside `embed()`; do not monkeypatch `AbstractInteractivePlot.embed` in content. `.embed()` only
produces a WASM app if the constructor is registered in `libdpy.visualization.registry` **and** that
registration has been released to `pub_lib` — an `.embed()` on an unregistered/unreleased class
renders nothing on the static site.

The build discovers `.embed()` calls by **static AST parsing** (`scripts/build_interactives.py`,
enforced by `tests/test_plot_inventory_scan.py`), so a call is exported only when its constructor
arguments are **keyword-only and literal**. Positional args, variables, computed expressions,
`**kwargs`, or a variable receiver are skipped:

| Discovered (works) | Skipped (fails) |
|---|---|
| `TheoryROCVisualizer(distribution='Gaussian', scale=1.0, …).embed()` | `TheoryROCVisualizer('Gaussian', scale=x, …)` — positional / variable |
| `PrivateEstimationAuditROCVisualizer(scene="ms-repair-one").embed()` | `EmpiricalEpsilonFromDeltaVisualizer(samples_neg=panel.samples_neg, …).embed()` — runtime arrays |
| | `viz = TheoryROCVisualizer(…); viz.embed()` — variable receiver |

Two consequences for ROC embeds are common enough to have their own patterns (below): audit panels
with runtime sample arrays, and theory plots with computed parameters.

**Animations** — use `content/**/animations/<name>.py` sidecars only. Embed generated artifacts
with `libdpy.visualization.animation_embed` helpers (GIF, player, or MP4 per `OUTPUTS`).

**Exceptions** — hand-written browser apps are allowed only with manifest `runtime:
external-app`, smoke tests, and a documented reason. Embed them with
`libdpy.visualization.external_app_embed.external_app_iframe` (not raw `<iframe>` tags).
Generated WASM bundles must not live under `content/**/apps/`.

Phase 0 inventory checks live in `libdpy.visualization.plot_inventory`. Pre-render strict checks
fail in `website/tests/test_plot_inventory_scan.py` and
`code_base_dev/tests/test_plot_inventory_scan.py`; post-render checks (doubled defer attributes,
full-page WASM route coverage) run after `quarto render`.

### Audit ROC embeds with fixed samples

Audit panels produce sample arrays at runtime, which cannot be passed as literals. Keep the samples
in `libdpy` behind a **string scene id** and register a fixed-scene wrapper:

- Live dev notebook: `EmpiricalEpsilonFromDeltaVisualizer(samples_neg=panel.samples_neg, …).show()`.
- Website blog post: `PrivateEstimationAuditROCVisualizer(scene="ms-repair-one").embed()`.
- Scenes and their deterministic sample generation live in
  `libdpy/assignment_specific/private_estimation/audit_embed_scenes.py` (`build_audit_embed_samples`),
  exposed via `PrivateEstimationAuditROCVisualizer` (`embed_interactives.py`) and registered in
  `libdpy.visualization.registry`. Current scene ids: `ms-repair-one`, `ms-repair-three`,
  `quantile-s3`.

### Theory ROC embeds with computed parameters

When ROC parameters are computed in earlier cells (e.g. a required noise scale), the website
`.embed()` call must use **baked numeric literals** — recompute them once from the dev notebook's
constants and paste the numbers in. Because they are literals, they **silently desynchronize** from
the narrative code if a shared constant (`DELTA`, `SEED`, a witness value) later changes; re-bake when
those move.

### Site-export constraints (library authors)

A site-exportable spec builder must produce a **JSON-serializable** `fixed_kwargs` (numpy arrays via
`.tolist()`), list `wasm-marimo` in `allowed_backends`, and — when `(n_neg, n_pos, delta)` alone
could collide — include a sample fingerprint in its `artifact_name`. Full list in
`code_base_dev/libdpy/ARCHITECTURE.md` (*Site export (WASM) constraints*); reference implementation:
`empirical_roc_from_samples_spec` in `libdpy/visualization/roc_plots.py`.
