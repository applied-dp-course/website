# Applied DP Course — Website Implementation Plan

Operational plan for building the course website. The **architecture** is fixed by
`applied-dp-course-website-plan.md` (v4, kept in this dir but git-ignored — it is the design
rationale, not a tracked artifact). This file is the *executable* plan: what we build, in what
order, and the one rule that governs every file in this repo.

---

## 0. Prime directive — the website holds **no implementation**

> **The website repo contains presentation and wiring only. Every line of computational logic —
> solvers, simulations, widgets, plotting, geometry, data loading — lives in `libdpy`
> (the `pub_lib` repo, `github.com/applied-dp-course/pub_lib`). The website *imports* `libdpy`
> exactly the way the course notebooks do.**

Concretely, in this repo:

- **Allowed:** `.qmd` slides/notes, `_quarto.yml`, `manifest.yml`, CI workflows, a thin
  `notebook.ipynb` whose code cells only `import` from `libdpy` and *call* its functions, and
  thin app entrypoints (marimo/JupyterLite) that do the same.
- **Forbidden:** any function/class that *computes* a result, any reconstruction/DP math, any
  widget definition, any plotting body, any dataset. If a slide needs new logic, that logic is
  added to `libdpy` first and imported here second.

The test for any cell or app file: *if you deleted `libdpy`, would this file still contain
domain logic?* If yes, it is in the wrong repo.

This mirrors the existing notebook contract:

```python
try:
    import libdpy
except ImportError:
    %pip install -q "libdpy @ git+https://github.com/applied-dp-course/pub_lib.git"  # local/Colab
    # browser (JupyterLite/marimo) installs the hosted WHEEL via micropip — never git+ (§1.1 of v4)
    import libdpy
```

---

## 1. Repository layout (this repo)

```text
website/
  _quarto.yml                      # site + RevealJS config, freeze: auto
  index.qmd  schedule.qmd  syllabus.qmd
  requirements.txt                 # HOST render env only (pulls libdpy from git)
  .github/workflows/publish.yml    # render + checks + deploy on push to main
  PLAN.md  STATUS.md               # this plan + live status (tracked)
  applied-dp-course-website-plan.md# v4 design rationale (git-ignored)
  lectures/
    02-reconstruction/             # FIRST interactive lecture (this milestone)
      slides.qmd                   # RevealJS; {{< embed >}} + iframes only
      notebook.ipynb               # canonical figures; import-only cells
      manifest.yml                 # per-lecture contract (v4 §6)
      apps/                        # marimo/JupyterLite entrypoints (import-only)
      assets/                      # generated static fallbacks (v4 §7)
```

No `lectures/**/` directory ever contains a Python *module* — only notebooks/qmd/apps that import
`libdpy`.

---

## 2. The `libdpy` contract for the reconstruction lecture

Everything the reconstruction lecture renders comes from these imports (verified against the dev
notebook `code_base_dev/lectures/lecture_reconstruction.ipynb`):

| Symbol | `libdpy` module | In public `pub_lib`? |
|---|---|---|
| `run_simulation`, `QueryMechanism`, `compute_average_error_for_noise_scale`, `perform_reconstruction_attack_mechanizm` | `libdpy.assignment_specific.reconstruction.reconstruction_utilities` | ✅ yes |
| `plot_reconstruction_error_as_noise_function` | `libdpy.assignment_specific.reconstruction.reconstruction_visualization` | ✅ yes |
| `choose_random_subset`, `get_mean_reconstruction_error` | `libdpy.attacks.reconstruction.reconstruction_attacks` | ✅ yes |
| `lin_prog_reconstruction`, `lin_reg_reconstruction`, `int_prog_reconstruction` | `libdpy.attacks.reconstruction.solvers` | ✅ yes |
| `interactive_2d_slab`, `plot_query_matrix_overview`, `plot_candidate_elimination_panels` | `libdpy.assignment_specific.reconstruction.reconstruction_lecture_visualization` | ✅ yes (on `origin/main`) |
| `interactive_3d_slabs`, `plot_3d_out_of_cube_example` | `libdpy.assignment_specific.reconstruction.reconstruction_3d_visualization` | ✅ yes (on `origin/main`) |
| geometry + instance helpers (`classify_corners_under_slabs`, `cube_corners`, …) | `libdpy.attacks.reconstruction.geometry`, `…instances` | ✅ yes (on `origin/main`) |

### 2.1 Library state — already public (verified 2026-06-15)

All reconstruction modules above are present on `pub_lib`'s `origin/main` (commit `ec7527b`),
and the course datasets are bundled into the installed package (commit `76152ae`, which addresses
the v4 §1.1 packaging risk for the source/git install). Since `main` is the remote's default
branch, the notebooks' `pip install "libdpy @ git+…pub_lib.git"` already pulls them — **no
library PR is required** for the host/local/Colab render path.

> Caveat that bit us once: a *local* `pub_lib` working copy can be behind `origin/main`. Judge
> the import surface against `origin/main` (`git fetch && git cat-file -e origin/main:<path>`),
> not the local checkout. The browser path still needs a hosted **wheel** (next paragraph).

The one remaining library-side gap is the **browser wheel** (v4 §1.1): `micropip`/`piplite`
install built wheels, not `git+`. Building and hosting a `libdpy` wheel (and confirming the
bundled CSVs survive the wheel build, not just the source install) is still required before any
Tier-2 (WASM) element runs in-browser. This is a packaging/release task, not new code.

---

## 3. Phased implementation

### Phase 0 — Runtime spike (de-risk before content) — v4 §14
Prove the browser path on a throwaway page deployed to Pages:
1. Quarto site deploys to GitHub Pages via Actions.
2. One `{{< embed notebook#label >}}` figure renders into a RevealJS deck.
3. One Tier-1 (Plotly/OJS) slider works with no kernel.
4. **`libdpy` installs in-browser from a hosted wheel via `micropip`/`piplite` — not `git+`** (v4 §1.1).
5. Packaged CSV loads in-browser via `importlib.resources`.
6. One `scipy.optimize.linprog(method="highs")` reconstruction runs in-browser.

Core path (4–6) blocks; widget-level failures *redirect* (iframe / Tier-1 rewrite / static
fallback), they do not stop the phase.

### Phase 1 — Site shell
`_quarto.yml`, `index/schedule/syllabus.qmd`, the lecture template, `publish.yml` (render +
link-check + large-file guard), legacy-PDF links, and the manifest→status-table generator stub.

### Phase 2 — Reconstruction lecture (this milestone — the first interactive example)
Library modules are already public (§2.1); the host/local render path is unblocked today. The WASM
slab apps additionally need the hosted libdpy wheel (v4 §1.1). Steps:

1. **Notebook (`notebook.ipynb`)** — install cell + import cell + labeled figure cells that *call*
   `libdpy` (`plot_reconstruction_error_as_noise_function(run_simulation(...))`,
   `plot_query_matrix_overview(...)`, `plot_candidate_elimination_panels(...)`,
   `plot_3d_out_of_cube_example(...)`). Each figure gets a `#| label: fig-*` for embedding. No
   logic defined in the notebook.
2. **Slides (`slides.qmd`)** — narrative + `{{< embed notebook.ipynb#fig-* >}}` for deterministic
   figures; `<iframe>` to the WASM apps for the live slabs; conditional static fallbacks for
   non-RevealJS exports (v4 §7).
3. **Apps (`apps/`)** — marimo/JupyterLite entrypoints that are *one import + one call*:
   `interactive_2d_slab()` and `interactive_3d_slabs()` from `libdpy`. Exported to WASM in CI.
4. **Fallbacks (`assets/`)** — generated from the notebook/app in CI (`marimo export html-wasm`
   for apps; notebook render for figures), never hand-drawn.
5. **Manifest (`manifest.yml`)** — fill the v4 §6 minimum-viable fields; `status: migrated` only
   once the §8 smoke tests pass against the deployed site.
6. **Smoke tests (v4 §8)** — `import libdpy`; load packaged CSV; run `lin_reg_reconstruction` and
   `lin_prog_reconstruction(method="highs")` small instances; slab widgets render in
   Chrome/Firefox/Safari.

### Phases 3–6
Lecture 1 interactive tables (k-anon/l-diversity/t-closeness) → hypothesis-testing ROC sliders →
authoring standardization → remaining lectures by pedagogical payoff (v4 §14). Each new lecture
follows the same import-only contract; each new piece of logic is a `pub_lib` PR first.

---

## 4. Tiering for the reconstruction lecture (v4 §5)

| Element | Tier | Source in `libdpy` |
|---|---|---|
| Reconstruction-error-vs-noise curve | 1 (static figure) or 2 (live slider) | `run_simulation` + `plot_reconstruction_error_as_noise_function` |
| Query-matrix / candidate-elimination panels | 1 (static figures) | `plot_query_matrix_overview`, `plot_candidate_elimination_panels` |
| 2-D feasible-region slab | 2 (WASM iframe app) | `interactive_2d_slab` |
| 3-D feasible-region slabs | 2 (WASM iframe app) + static 3-D snapshot fallback | `interactive_3d_slabs`, `plot_3d_out_of_cube_example` |

Interactivity only where it changes what students can *infer* (v4 §5 pedagogy rule): the slabs
(feasible region shrinking as queries accumulate) and the error-vs-noise tradeoff qualify;
expository slides stay static.

---

## 5. Definition of done — reconstruction milestone

- [ ] `interactive_3d_slabs()` runs from a clean public install (already on `origin/main`; verify
      the local `pub_lib` is synced before relying on it locally).
- [ ] `notebook.ipynb` renders all `fig-*` outputs with import-only cells.
- [ ] `slides.qmd` embeds figures + iframes the two slab apps + ships static fallbacks.
- [ ] Both apps export to WASM in CI and load within the v4 §9 budgets.
- [ ] `manifest.yml` complete; v4 §8 smoke tests pass on the **deployed** Pages site in 3 browsers.
- [ ] No domain logic anywhere under `lectures/02-reconstruction/` (prime-directive grep clean).
```
