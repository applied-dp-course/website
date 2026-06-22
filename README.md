# Applied Differential Privacy — Course Website

Static [Quarto](https://quarto.org) site, published to GitHub Pages, for the *Applied
Differential Privacy* course: lecture decks, self-study notebooks, assignments, interactive
widgets, a blog, and a tools gallery.

- **Authoring** (add a lecture / assignment / tool / post, start a new term): see
  [`authoring/AUTHORING.md`](authoring/AUTHORING.md).

---

## Core principle — this repo holds presentation and wiring only

Every line of computational logic — DP math, reconstruction solvers, plotting, widgets, data
loading — lives in **[`libdpy`](https://github.com/applied-dp-course/pub_lib)** (the `pub_lib`
repo). The website *imports* `libdpy` exactly the way the course notebooks do. If a slide needs
new logic, that logic is added to `libdpy` first and imported here second.

> **Test for any cell or app file:** if you deleted `libdpy`, would this file still contain
> domain logic beyond tiny toy inputs and render parameters? If yes, it is in the wrong repo.

---

## Architecture

- **Quarto → GitHub Pages via Actions.** Notebooks/`.qmd` render to HTML and RevealJS;
  `execute: freeze: auto` skips re-executing unchanged notebooks.
- **Three decoupled content layers:**
  - **Catalog** (shared, reusable across terms): `content/lectures/`, `content/assignments/`,
    `tools/`. Each lecture exposes two surfaces — a self-study notebook (`learn.ipynb`) and a
    presentation deck (`slides.qmd`, or notebook-first `notebook.ipynb`).
  - **Offering** (one config per course iteration): `content/offerings/<term>/`
    (`offering.yml` + `schedule.csv`). `content/course.yml` names the `current_offering`.
  - **General** (course-independent): `blog/` posts and standalone `tools/`.
- **Generated index pages.** `schedule`, `lectures`, `assignments`, `tools`, and `archive`
  `.qmd` pages carry `BEGIN/END AUTO-GENERATED` marker sections that `scripts/sync_content.py`
  fills from the catalog + the current offering. The current term drives Home and Schedule;
  past terms re-render from the same shared catalog and appear under Archive.

## Interactivity

Widgets ship as **static client-side WASM** (marimo + Pyodide) — free on GitHub Pages, and they
never rot. `PrivacyPlot(...).embed()` calls in lecture/blog/tool sources are discovered by
`scripts/build_interactives.py` and exported to self-contained apps under `apps/`. `libdpy` and
`plotly` are bundled into a single same-origin wheel installed in-browser via `micropip`.
Cold first-load is mitigated by a click-to-load placeholder. (A live marimo server is a possible
future step; embeds use an iframe indirection so it can be swapped in without a rewrite.)

---

## Repository map

```text
_quarto.yml                     site shell: nav, theme, render globs, pre/post-render hooks
index.qmd syllabus.qmd about.qmd  hand-written shell pages
schedule.qmd lectures.qmd        GENERATED index pages (marker sections filled by sync_content.py)
  assignments.qmd tools.qmd archive.qmd
theme/                          academic restyle (custom.scss)
content/
  course.yml                    course-wide config (current_offering, colab, instructors)
  offerings/<term>/             offering.yml + schedule.csv, one per course iteration
  lectures/NN-slug/             learn.ipynb (+ slides.qmd / notebook.ipynb), manifest.yml, apps/, assets/
  assignments/<slug>/           assignment.ipynb, manifest.yml, [solution.ipynb — private, git-ignored]
blog/posts/<slug>/              standalone posts (Quarto listing)
tools/<slug>/                   standalone interactive tool pages (gallery sources)
scripts/                        content sync, interactive build, site checks
tests/                          unit tests + headless-Chrome browser smoke tests
authoring/                      teacher-facing guide + templates + tutorials (NOT published)
dev/                            local helper scripts + test fixtures (NOT published)
generated/ _site/ _freeze/      build artifacts (git-ignored)
.github/workflows/publish.yml   CI: build wheel + render → tests → deploy to Pages → verify
```

---

## Build & preview locally

Requires Python 3.11 and Quarto 1.6.43.

```bash
# One-time: create the venv (installs libdpy from pub_lib via requirements.txt)
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Render the whole site (executing notebooks) into _site/
./dev/tools/render.sh
# equivalently:
#   QUARTO_PYTHON="$(pwd)/.venv/bin/python" MPLBACKEND=Agg quarto render --execute

# Preview
./dev/tools/preview.sh        # or: ./.venv/bin/python -m http.server --directory _site
```

## Tests

```bash
./.venv/bin/python scripts/content_model.py     # metadata validation (also the first pre-render step)
./.venv/bin/python -m pytest tests -q           # unit + build tests
./.venv/bin/python tests/run_smoke_tests.py     # headless-Chrome WASM/canvas smoke tests (needs a prior render)
```

## CI / deployment

`.github/workflows/publish.yml` on push to `main`: builds the `libdpy` wheel and renders the site
(pre-render hook) → unit tests → `scripts/check_site.py` (routes/redirects/links) →
headless-Chrome WASM + canvas smoke tests → deploy to GitHub Pages → verify deployed routes.

---

## Build gotchas (encoded so they are not re-learned)

1. **Project format must be `html`-only in `_quarto.yml`.** Declaring `revealjs` at the *project*
   level renders every page to both formats; the revealjs pass also emits `index.html`, which
   collides during the `_site` move → a `safeMoveSync` "No such file" crash that aborts the build.
   A deck sets `format: revealjs` in its **own front matter**. (Reproduced on Quarto 1.6.43 and
   1.9.38 — it is the config, not the version.)
2. **`%matplotlib inline` is required** in any lecture notebook. Without it IPython does not
   register the PNG figure formatter, so `plt.show()` / `display(fig)` emit only `text/plain` and
   `{{< embed >}}` fails with "doesn't contain output to embed".
3. **Quarto globs recurse by default.** Anchor render/resource globs to the project root with a
   leading `/` (e.g. `/*.qmd`), or sources under `authoring/`/`dev/` get published.
4. **A local `pub_lib` checkout can lag `origin/main`.** Judge the import surface against the
   remote, not the local working copy.
5. **The browser path needs a built wheel, not `git+`.** `micropip`/`piplite` install built
   wheels; the WASM apps install the bundled same-origin `libdpy` wheel (which also vendors
   `plotly`), never a `git+` URL. Local/Colab notebooks may keep the `git+` install.
