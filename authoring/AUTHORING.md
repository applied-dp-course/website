# Authoring guide

> **Human-developer reference.** How *agents* operate (delivery discipline, isolate-don't-loop,
> stop-loss) is in [`../../AGENTS.md`](../../AGENTS.md); this guide covers *how website authoring
> works*. The *Delivery gate* and *Isolating failures* sections below are the mechanics both humans
> and agents follow.

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

**Same-commit checklist** (CI runs `./.venv/bin/python -m pytest tests -q` before render):

1. Append the item's rendered HTML path to
   [`dev/plan/baseline-routes.json`](../dev/plan/baseline-routes.json) — required even for
   `status: draft` items (draft decks still build and appear in `required_routes()`).
2. If the item is a lecture presentation, blog post, or class assignment, update the expected
   name sets in `tests/test_content_model.py::test_live_catalog_uses_named_collections`.
3. If the source imports **new** `libdpy` API, implement it in `code_base_dev/libdpy/` first
   (*Content that depends on a new `libdpy` API* below) — including draft decks that call new
   `make_*_figure()` helpers. Release to `pub_lib` is for the student pip path only, not required
   to render locally or in CI.

Example baseline entry for `content/lecture-presentations/mechanisms/presentation.qmd`:

```text
content/lecture-presentations/mechanisms/presentation.html
```

### Content that depends on a new `libdpy` API

The site installs `libdpy` **editable from sibling `code_base_dev/libdpy`**, and
`./dev/tools/render.sh` runs `sync_libdpy.sh` before rendering. Content using **any** library API
not yet in that tree — a new function, a new keyword argument, or a newly registered interactive —
will fail to build until you implement it in `code_base_dev/libdpy/` and sync. No `pub_lib` release
is required to iterate locally or in CI.

**Student pip installs** still use pinned `pub_lib` tags. When students need the new API, release
via `code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md` and update `requirements-pub-lib-pin.txt`
(not `requirements.txt`). For a deliberate skip of re-sync, use `LIBDPY_SYNC=0 ./dev/tools/render.sh`.

The trigger is not only new kwargs: **adding a new class to `EMBED_CONSTRUCTOR_NAMES`**
(`libdpy.visualization.registry`) is itself a library change — implement and register it in
`code_base_dev/libdpy/` before its `.embed()` calls resolve on the site.

## Developing a lecture (end to end)

A lecture ships two authored artifacts — `blog-posts/<slug>/post.ipynb` (self-learning) and
`lecture-presentations/<slug>/presentation.qmd` (deck) — both derived from the private dev notebook
`code_base_dev/lectures/lecture_<topic>.ipynb` and importing the same `libdpy` helpers. The dev
notebook is the permanent source and is **never deleted**; the two website copies are kept in
parallel (drift accepted — the blog-post smoke route is the tripwire).

**Preconditions.** The tree is green (content validation + the plot-inventory scan pass on `main`),
and every `libdpy` API the content uses exists in sibling `code_base_dev/libdpy/` — implement
there first if needed (*Content that depends on a new `libdpy` API* above).

**Steps.** Author both artifacts (*Add content*) → use `.embed()` for interactives (*Plotting
policy*) → validate with `./dev/tools/render.sh` then `./.venv/bin/python tests/run_smoke_tests.py`
(*Validation*), confirming `_generated/apps/**/<slug>/…` WASM and green smoke for both routes → add
the slug to `content/offerings/<term>/schedule.csv` and set both manifests to `published`.

**Deck vs blog interactives.** The two artifacts need not carry the same interactives. The
convention (applied to private-estimation): the **deck** uses static `make_*_figure()` factories for
speed and print-safety, while the **blog post** carries the interactive `.embed()` explorers — not
every interactive in the dev notebook must appear in both.

### In-flight lectures (stricter alignment)

Once a lecture passes the delivery gate (below), the dev notebook may drift from the website
copies and should move to
[`code_base_dev/lectures/migrated/`](../../code_base_dev/lectures/migrated/README.md) — a
post-ship bookkeeping step in the private repo, not part of the website commit. **While a
lecture is still in active development**, keep the dev notebook in
`code_base_dev/lectures/` and treat alignment as mandatory:

| Artifact | Role |
|---|---|
| `code_base_dev/lectures/lecture_<topic>.ipynb` | Authoring source — never delete |
| `blog-posts/<slug>/post.ipynb` | Self-study copy — same `libdpy` symbols and public contract |
| `lecture-presentations/<slug>/presentation.qmd` | Deck copy — same mechanism names, budgets, seeds, sampling params |

Narrative density and interactives may differ (see *Deck vs blog interactives*), but imports and
public constants must match the **in-tree** `libdpy` install (`sync_libdpy.sh`).

**Do not use quarantined generators.** Scripts under `dev/tools/quarantine/` are not part of the
delivery path — they may be stale or hand-maintained. Align blog and deck manually against the dev
notebook until a generator ships with a deterministic `--check` mode.

**Pre-ship checklist:**

- Dev notebook, blog, and deck import only symbols present in sibling `code_base_dev/libdpy/`.
- Run `./dev/tools/sync_libdpy.sh`, then confirm `libdpy.__file__` resolves (import succeeds).
- Run `./.venv/bin/python dev/tools/verify_libdpy_imports.py --slug <slug>` (add `--sync` to
  install libdpy first).
- Pass `./dev/tools/deliver_lecture.sh --slug <slug>`.

### Delivery gate (definition of “shipped”)

**Infra go-live and lecture go-live are different.** A green deploy of CI/release-flow changes, or a
successful `pub_lib` tag push, does **not** mean a lecture slug is shipped. Do not report a lecture
as done until the gates below pass on **that slug’s commit**.

**Keep website copies aligned with the dev notebook.** The dev notebook is the authoring source;
`presentation.qmd` and `post.ipynb` are parallel copies that **will drift** if refactored separately.
After changing `libdpy` figure helpers or imports in the dev notebook, update both website artifacts
to import the **same symbols** from the in-tree install.

**Order for a lecture that needs new library API:**

1. Implement and test in `code_base_dev/libdpy/` (`pytest` green on affected tests).
2. Update website deck + blog post to match the current API.
3. Run the **delivery gate** below (`./dev/tools/sync_libdpy.sh` installs the sibling tree).
4. Push website `main` (or merge a PR whose `build-check` passed).
5. When students need the new API, tag `code_base_dev` (`vX.Y.Z`), confirm `pub_lib` has the tag,
   and update `requirements-pub-lib-pin.txt`.

Do **not** push website content that imports symbols missing from sibling `code_base_dev/libdpy/`.

**Delivery gate — run the orchestrator; do not hand off.** `./dev/tools/deliver_lecture.sh`
executes every step below fail-closed and, with `--push`, blocks until CI deploys the content
commit to Pages. A local render passing or a `pub_lib` tag existing is **not** shipping. When the
gate fails or you learn something isolating a slug, add an entry to
[`code_base_dev/DEVELOPMENT/DEV_LOG.md`](../../code_base_dev/DEVELOPMENT/DEV_LOG.md) during the
work — not only after a successful push.

```bash
# from website/ — validate only (no push):
./dev/tools/deliver_lecture.sh --slug <slug>

# validate, then push and block on a GREEN build+deploy (optionally confirm the live page):
./dev/tools/deliver_lecture.sh --slug <slug> --push \
    --base-url https://applied-dp-course.github.io/website/<route> --expect "<deck title>"
```

The gate runs, in order, and stops at the first failure:

1. **Preconditions** — the slug is registered (content dir + `dev/plan/baseline-routes.json` +
   `tests/test_content_model.py`); clean tree required when `--push`.
2. **Library** — `sync_libdpy.sh` (sibling `code_base_dev/libdpy`); then
   **`verify_libdpy_imports.py`** — the fast API-drift tripwire that resolves every libdpy symbol
   the deck/post import against the installed package, in seconds, *before* the ~7-minute render.
3. **Validate** — `pytest tests` → full `render.sh` → `check_site.py` → `run_smoke_tests.py --slug`.
4. **Publish** (`--push` only) — push, then `gh run watch` the *Publish website* build+deploy to
   green; optional live-URL check.

#### Isolating failures (debug loop discipline)

`deliver_lecture.sh` runs the full validate step (pytest → **site-wide** `render.sh` → smoke) and
stops at the first failure. Use it as the **final** confirmation before push — not as the inner
loop while fixing one slug or one WASM app. Re-running it after every tweak burns ~10–15 minutes per
attempt and re-renders all targets even when only one slug is broken.

When smoke fails on one slug, narrow scope before touching the orchestrator:

1. **Import / API drift** — `./.venv/bin/python dev/tools/verify_libdpy_imports.py --slug <slug>`
   (seconds).
2. **Scoped smoke** — `./.venv/bin/python tests/run_smoke_tests.py --slug <slug>` after a
   slug-scoped render or `build_interactives.py` rebuild (*Validation → Incremental loop*).
3. **Single per-app WASM** — serve `_generated/apps/.../<artifact>/index.html` and run
   `tests/smoke_wasm_browser.py` against that URL, or pass `--include-per-app` to scoped
   `run_smoke_tests.py` for one artifact.
4. **Manual browser** — only when headless smoke is ambiguous (timing, focus, or a new control
   type).

Do **not** re-run `deliver_lecture.sh` (or a cold full `render.sh`) until the isolated check for
the failing slug passes. When multiple slugs are in scope, fix and verify one slug at a time; run
the full gate once at the end.

**Smoke harness changes** (`tests/smoke_wasm_browser.py`, `smoke_full_page_wasm.py`) are a last
resort. Prefer fixing `libdpy` reactive wiring or website content. If the harness must change, state
the product bug vs test gap explicitly and get human approval — do not patch assertions to green a
known broken interactive.

**Stop-loss — when isolation shows an *open problem*, not a hidden one.** The ladder above finds a
fix that already *exists*. If the isolated per-app check keeps failing because the behavior itself
is unknown (e.g. a WASM/marimo interactive that will not redraw — reconstruction, 2026-07-03), you
have crossed from debugging into R&D: **stop looping.** Confirm the root cause once, then take the
plan's pre-committed fallback (e.g. ship the visual as a static `make_*_figure`) or escalate with a
short options list — do **not** tag a release on an unproven fix or re-run the full gate hoping it
changes. Uncertain interactive work belongs in a bounded spike **off** the delivery critical path;
decouple it so the other slugs ship (agent operating rules: [`../../AGENTS.md`](../../AGENTS.md)
§4–5).

**After the gate passes**, move the dev notebook from `code_base_dev/lectures/` to
`code_base_dev/lectures/migrated/` (never delete it). Update any hard-coded paths in tests or
scripts. In-flight lectures without shipped website content stay in `lectures/` — see
[../../code_base_dev/lectures/migrated/README.md](../../code_base_dev/lectures/migrated/README.md)
for the slug mapping table.

Run the drift tripwire on its own any time you refactor a `libdpy` helper (fails in seconds):

```bash
./.venv/bin/python dev/tools/verify_libdpy_imports.py --slug <slug>   # omit --slug to scan all content
```

When `libdpy` changed, run its unit tests on the library side before releasing/tagging:

```bash
~/venvs/libdpy/dev-local/bin/python -m pytest tests/test_<topic>.py -q
```

**CI cache caveat.** A green deploy on `main` that only touched infra may not have rendered your
lecture. CI render cache and incremental WASM skips can hide stale artifacts. Before calling a
lecture shipped, a **full** local `./dev/tools/render.sh` on the content commit is required; do not
infer lecture health from an unrelated green workflow run.

**Common delivery pitfalls (do not repeat):**

| Pitfall | Symptom | Guard |
|---------|---------|-------|
| Warm local cache hides a cold CI render | Local `./dev/tools/render.sh` passes; **Publish website** fails on `build_interactives` / gallery | After WASM or gallery changes, simulate CI: `rm -rf _freeze _generated _site && ./dev/tools/render.sh` |
| Shared WASM artifact, one export path | Gallery error: manifest path missing under `_generated/apps/lecture-presentations/...` | One `.embed()` in several sources (home page + deck + blog) needs a bundle at **each** source-relative `_generated/apps/<parent>/` path; `build_interactives.py` exports once and copies to every location |
| API drift on installed libdpy | ~7-minute render fails mid-notebook | Run `./.venv/bin/python dev/tools/verify_libdpy_imports.py --slug <slug>` first (CI runs this before render) |
| Stale libdpy in `.venv` | Local checks pass against old API; sync needed | Run `./dev/tools/sync_libdpy.sh` after changing `code_base_dev/libdpy/` |
| Static-figure lecture | `run_smoke_tests.py --slug` exits: "no full-page WASM routes match" | Expected for deck-only static figures — scoped smoke no-ops; still run the full gate before push |
| Infra green ≠ lecture shipped | Tag on `pub_lib` exists or CI passed on an infra-only commit | Use `./dev/tools/deliver_lecture.sh --slug <slug> --push` and wait for **Publish website** green on the **content** commit |
| Full gate as debug loop | Hours spent re-rendering; one slug still red | Isolate per slug → per-app WASM → manual browser (*Isolating failures* above); run `deliver_lecture.sh` once when scoped checks pass |
| Smoke harness band-aid | Assertions loosened; product still broken in browser | Fix `libdpy`/content; document a known exemption with human approval instead of patching smoke |

**Simulate CI before push** when you touched WASM exports, gallery manifests, or shared embeds:

```bash
rm -rf _freeze _generated _site
./dev/tools/deliver_lecture.sh --slug <slug>    # validate only; add --push when clean tree is green
```

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

CI (`.github/workflows/publish.yml`) runs, in order: **unit tests** → **render** → **route
checks** → **WASM smoke** → deploy. A failure in the first step completes in under a minute; check
Actions logs for the failing pytest name before assuming a render or browser issue.

```bash
./.venv/bin/python scripts/content_model.py
./.venv/bin/python -m pytest tests -q
./dev/tools/render.sh
./.venv/bin/python tests/run_smoke_tests.py
```

The first pytest command mirrors CI's pre-render gate. Run it after adding or renaming content
(*Add content* → same-commit checklist).

Validation rejects numbered content names, missing entrypoints, wrong source types, offering
references that do not match an authored content name, and **notebooks whose `kernelspec.name` is not
`python3`** (CI rejects e.g. `libdpy-base-local` — reset the kernel to `python3` before committing).
`run_smoke_tests.py` is the **required final gate for any content with interactives** — it opens the
rendered WASM apps in a headless browser and must pass before the content is considered done.

**Baseline routes.** `tests/test_baseline_routes.py` compares the live catalog's
`required_routes()` against [`dev/plan/baseline-routes.json`](../dev/plan/baseline-routes.json).
Whenever you add a content item under `content/lecture-presentations/`, `content/blog-posts/`,
`content/class-assignments/`, or `content/home-assignments/`, append its `.html` route to
`required_routes` in that file in the **same commit** — including `status: draft` decks.

**In-tree `libdpy` dependency.** CI checks out sibling `code_base_dev` and runs
`sync_libdpy.sh` during *Install Python dependencies*, before unit tests. The website repo needs
the `CODE_BASE_DEV_CHECKOUT_TOKEN` secret (contents:read on `code_base_dev`). Student pip installs
still use `pub_lib` — see `requirements-pub-lib-pin.txt` and
`code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md`.

**Incremental (single-lecture) loop.** The four commands above are the full "done" gate; while
iterating on one lecture, a faster loop avoids the site-wide render + smoke:

```bash
./.venv/bin/python -m pytest tests/test_plot_inventory_scan.py -k pre_render
./.venv/bin/python scripts/build_interactives.py                 # rebuild WASM apps only
quarto render content/blog-posts/<slug>/post.ipynb               # render one notebook
./.venv/bin/python tests/run_smoke_tests.py --slug <slug>        # scoped full-page smoke
```

The scoped smoke command runs only the matching full-page WASM routes and skips the
site-wide per-app loop (each app can take up to five minutes locally). Static-figure slugs with
no WASM embeds no-op instead of failing. Use
`tests/smoke_full_page_wasm.py` against a served URL for an even lighter check while
iterating; pass `--include-per-app` to `run_smoke_tests.py` if you also need the
standalone per-app pass.

A full `./dev/tools/render.sh` is still required before "done" when artifact names change, animation
sidecars are added/changed, or offering/page sync is affected. See *Developing a lecture → Delivery
gate* for the full “shipped” definition and the anti-pattern of treating infra deploy success as
lecture completion.

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
registration exists in sibling `code_base_dev/libdpy/` — an `.embed()` on an unregistered class
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
