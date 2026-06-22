# Authoring guide — Applied Differential Privacy course site

This repository separates three layers:

- **Catalog** — shared lectures (`content/lectures/`), assignments (`content/assignments/`), and
  standalone tools (`tools/`).
- **Offering** — one term config under `content/offerings/<term>/` (dates, schedule, logistics).
- **General content** — blog posts (`blog/`) that are course-independent.

All computation lives in [`libdpy`](https://github.com/applied-dp-course/pub_lib). Course materials
here import from that library only.

Templates for each content type live in `authoring/templates/`. Copy a template directory, rename it,
fill in metadata, and run the validation commands below before opening a pull request.

---

## Quick validation

From the repository root (with `.venv` activated):

```bash
# Metadata only — fast fail before Quarto
./.venv/bin/python scripts/content_model.py

# Full site build
./dev/tools/render.sh

# Unit tests
./.venv/bin/python -m pytest tests -q

# Browser smoke tests (requires a prior render)
./.venv/bin/python tests/run_smoke_tests.py
```

`content_model.py` runs automatically as the first `_quarto.yml` pre-render step. If metadata is
invalid, the build stops before expensive WASM exports.

---

## Start a new offering

1. Copy the template directory:
   ```bash
   cp -R authoring/templates/offering content/offerings/2027-spring
   ```
2. Edit `content/offerings/2027-spring/offering.yml` (label, dates, meeting, staff, announcements).
3. Edit `content/offerings/2027-spring/schedule.csv` — one row per week. Columns:
   `week,date,topic,lecture,presentation,assignment,notes`. Lecture and presentation cells reference
   lecture slugs; assignment cells reference assignment slugs. Empty cells are allowed.
4. Point the live site at the new term in `content/course.yml`:
   ```yaml
   current_offering: 2027-spring
   ```
5. Run `./.venv/bin/python scripts/content_model.py`, then `./dev/tools/render.sh`.

Past offerings remain listed on **Archive**; only `current_offering` drives Home, Schedule, and
assignment due dates.

---

## Add a lecture

Directory name must be `NN-slug` (e.g. `04-mechanisms`).

1. Copy templates:
   ```bash
   cp -R authoring/templates/lecture content/lectures/04-mechanisms
   ```
2. Edit `manifest.yml` — title, number, subjects, and both surfaces (`learn.ipynb`, `slides.qmd`).
3. Author the self-study notebook (`learn.ipynb`) and presentation deck (`slides.qmd` or, for
   notebook-first RevealJS, `notebook.ipynb` declared under `surfaces.presentation`).
4. Optional interactives:
   - **WASM widgets** — call `PrivacyPlot(...).embed()` in a notebook or qmd; the build exports them
     automatically.
   - **Browser-native apps** — add hand-authored HTML under `apps/<id>/` and declare the app in
     `manifest.yml` under `apps:` (or legacy `runtimes.apps` string list).
5. Add the lecture slug to the current offering's `schedule.csv`.
6. Validate and render (commands above).

Each lecture exposes two public surfaces: a self-study page and a presentation deck. Colab badges are
generated from `content/course.yml` when `colab.enabled` is true.

---

## Add an assignment

1. Copy templates:
   ```bash
   cp -R authoring/templates/assignment content/assignments/my-assignment
   ```
2. Edit `manifest.yml` — title, subjects, estimated time, related lecture slugs, notebook filename.
3. Author `assignment.ipynb`. Keep the Colab install cell as the first code cell:
   ```python
   try:
       import libdpy
   except ImportError:
       %pip install -q "libdpy @ git+https://github.com/applied-dp-course/pub_lib.git"
       import libdpy
   ```
4. Optional `solution.ipynb` for staff — **never commit it** (git-ignored; excluded from Quarto render).
5. Reference the assignment slug in `schedule.csv` for the due week.
6. Validate and render.

Due week and date on the Assignments page come from the schedule, not the assignment manifest.

---

## Add a standalone tool

1. Copy templates:
   ```bash
   cp -R authoring/templates/tool tools/my-tool
   ```
2. Edit `manifest.yml` and `index.qmd`. Set `gallery: true` to list the tool on **Tools**.
3. Optional WASM widget — same `PrivacyPlot(...).embed()` pattern as lectures.
4. Validate and render. The Tools page refreshes from `generated/gallery.json` after interactives build.

---

## Add a blog post

1. Create a post directory:
   ```bash
   mkdir -p blog/posts/my-post
   cp authoring/templates/blog/index.qmd blog/posts/my-post/index.qmd
   ```
2. Set `title`, `description`, `date`, and `categories` in the YAML header.
3. Write the post body. Posts may embed the same interactives as lectures.
4. Render — Quarto picks up new posts via the listing on `blog/index.qmd`.

Blog content is course-independent and is not tied to `schedule.csv`.

---

## Slide authoring sandbox

For experimenting with RevealJS slide styling, use the local tutorial under
`authoring/tutorials/slide-authoring/` (not published on the course site):

```bash
./dev/tools/render-slide-tutorial.sh
# open _site/authoring/tutorials/slide-authoring/tutorial.html after previewing the site, or:
./dev/tools/preview.sh
```

See the tutorial notebook for slide boundaries, CSS hooks, and the edit → render → refresh loop.

---

## What not to publish

These paths are for authors and developers only — they are excluded from `_quarto.yml` render globs:

- `authoring/` — templates and tutorials
- `dev/` — local helper scripts and test fixtures

Private assignment solutions (`content/assignments/**/solution.ipynb`) are git-ignored and blocked
from `_site/` by `scripts/assert_private_content.py`.

Project overview lives in [`README.md`](../README.md).

---

## Pull-request checklist

- [ ] `./.venv/bin/python scripts/content_model.py` passes
- [ ] `./.venv/bin/python -m pytest tests -q` passes
- [ ] `./dev/tools/render.sh` succeeds
- [ ] New catalog slugs appear in `schedule.csv` when scheduled
- [ ] Colab badges open valid GitHub blob URLs (when Colab is enabled)
- [ ] No `solution.ipynb` or `authoring/` / `dev/` artifacts under `_site/`
