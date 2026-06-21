# Full Course Website Structure — Applied Differential Privacy

## Context

The repo already has a working Quarto site with a real pipeline (notebook/qmd → web,
`PrivacyPlot().embed()` → marimo/WASM apps, headless-Chrome smoke tests, GitHub Pages deploy). All
computation lives in the external `libdpy` (import-only contract). Lectures 2 and 3 exist with the
notebook→web + RevealJS pattern.

This plan **expands and reorganizes** that foundation into a full course site with clearly
delineated components. Requirements driving the design:

- **Two surfaces per lecture** — a notebook "blog-post" self-study page (`learn.ipynb` → HTML) and
  a presentation deck (`slides.qmd` → RevealJS) — plus a **class-assignment link**.
- **Assignments are a separate, subject-organized catalog** (not co-located in lecture dirs).
- A teacher-edited **`schedule.csv` binds each week** to a chosen `{lecture, presentation,
  assignment}`. Site generates the **Schedule** (by week) and an **Assignments** tab (by subject).
- **Colab** runtime: every lecture & assignment notebook gets an *Open in Colab* badge
  (`pip install libdpy`).
- **Multiple course iterations** — one live current course + browsable **past offerings**. Chosen
  model: a **config layer** (per-term config over a shared catalog), live-rebuilt from the current
  catalog; current term is the homepage, an Archive page lists prior terms.
- **General standalone content** — a **Blog** and an interactive-**Tools** gallery as **separate
  top-level sections**, course-independent, for people interested in just one component.
- **Standalone tutorials** — learn notebooks usable on their own.
- **Interactivity**: ship **static WASM** (+ build-time precompute) for *all* widgets now — works
  free on GitHub Pages and never rots (current term and archives alike). A **live marimo server** for
  the current term (faster, no cold-load) is **deferred to a future step**, since GitHub Pages can't
  host a backend; embeds use a small indirection so it can be added later without rework.
- **Quarto is committed** — reuse the existing pipeline; no framework change.

Core idea: decouple three layers — a **shared catalog** (subject-tagged lectures/assignments), a
thin **offering** config per term (which items, which weeks, term logistics), and **general
content** (blog/tools) that stands apart from any term.

---

## Target directory layout

```
website/
├── _quarto.yml                      # [1] site shell: nav, theme, render globs
├── index.qmd  syllabus.qmd          # [1] hand-written shell pages (+ generated current-term banner)
├── schedule.qmd lectures.qmd        # [1] GENERATED index pages (marker sections)
│   assignments.qmd tools.qmd        #     (assignments, tools gallery, archive are new)
│   archive.qmd                      #
├── theme/                           # [1] academic restyle: custom.scss + small partials
│
├── scripts/                         # [2] conversion + generation infrastructure (auto-run by build)
│   ├── sync_content.py              #     (was sync_lectures.py) catalog + offerings + schedule + pages
│   ├── build_interactives.py        #     widget → WASM (scans lectures/blog/tools; emits gallery.json)
│   ├── run_site_python.py
│   └── colab.py                     #     compute Open-in-Colab URLs from content/course.yml
├── tests/                           # [2] unit + WASM smoke tests (paths updated)
│
├── content/                         # [3] course materials the teacher uploads
│   ├── course.yml                   #     course-wide: title, repo, colab base, instructors, current_offering
│   ├── offerings/<term>/            #     ONE small config per iteration of the course
│   │   ├── offering.yml             #       term label, dates, meeting info, announcements, grading notes
│   │   └── schedule.csv             #       week → {lecture, presentation, assignment}
│   ├── lectures/{NN}-{slug}/        #     SHARED catalog: learn.ipynb, slides.qmd, slides.css, manifest.yml, apps/, assets/
│   └── assignments/{slug}/          #     SHARED catalog: assignment.ipynb, manifest.yml, [solution.ipynb], assets/
│
├── blog/                            # [3-general] standalone, course-independent
│   ├── index.qmd                    #     Quarto listing page
│   └── posts/<slug>/index.{qmd,ipynb}#    posts may embed the same widgets
├── tools/                           # [3-general] standalone interactive tool pages (gallery sources)
│   └── <slug>/index.qmd + manifest.yml
│
├── authoring/                       # [4] shared docs, templates, scripts FOR THE TEACHER
│   ├── AUTHORING.md                 #     add lecture/assignment, edit schedule.csv, start a new offering
│   ├── templates/                   #     lecture-/assignment-/tool-/post- templates + manifest stubs
│   └── tutorials/slide-authoring/   #     moved from tutorials/
│
├── dev/                             # [5] development plan + tools
│   ├── plan/                        #     PLAN.md, design docs, decision briefs (tracked)
│   └── tools/                       #     local dev helper scripts (render recipe, preview)
│
├── generated/ _site/ _freeze/       # build artifacts (git-ignored)
└── .github/workflows/publish.yml    # CI/deploy
```

Five required dirs: **[1]** shell + `theme/`, **[2]** `scripts/` + `tests/`, **[3]** `content/`
(+ standalone `blog/`, `tools/`), **[4]** `authoring/`, **[5]** `dev/`.

---

## Content model: catalog · offerings · general

**Catalog (shared, subject-tagged, reusable across terms)**
- *Lecture* dir exposes two surfaces: `learn.ipynb` and `slides.qmd`; `manifest.yml` gains
  `subjects: [...]`.
- *Assignment* dir: `assignment.ipynb` + `manifest.yml` (title, `subjects`, est. time, related
  lectures). Optional `solution.ipynb` is **git-ignored / private**.

**Offering (one per course iteration)** — `content/offerings/<term>/`:
- `offering.yml`: term label, start/end dates, meeting time/place, announcements, per-term staff.
- `schedule.csv`:
  ```csv
  week,date,topic,lecture,presentation,assignment,notes
  1,2026-10-20,Reconstruction attacks,02-reconstruction,02-reconstruction,,
  2,2026-10-27,DP as hypothesis testing,03-hypothesis_testing,03-hypothesis_testing,hypothesis-testing-hw,
  3,2026-11-03,Reading week,,,,No class
  ```
  `lecture`/`presentation` reference a lecture slug; `assignment` references an assignment slug; any
  cell may be empty.
- `content/course.yml` carries `current_offering: <term>`. The build renders the current term's
  schedule as the live **Schedule** page; past terms re-render from the **same shared catalog**
  (content can drift — accepted trade-off of the chosen "live rebuild" model).

**General content (standalone)** — `blog/` (Quarto listing) and `tools/` (one page per standalone
interactive tool). Both are course-independent and discoverable on their own; both may embed widgets
via the existing `.embed()` pipeline. The **Tools** page aggregates standalone `tools/` plus every
lecture-embedded `apps/` widget.

**Generated pages** (each via the existing `BEGIN/END AUTO-GENERATED` marker +
`_replace_generated_section`):
- `schedule.qmd` — week table for the **current** offering (date, topic, lecture, slides,
  assignment, Colab badges).
- `archive.qmd` *(new)* — index of all offerings; each **past** term rendered as a collapsible
  inline week table (no per-term file sprawl).
- `lectures.qmd` — catalog grouped by subject; standalone-tutorial + deck links + Colab.
- `assignments.qmd` *(new)* — assignments grouped by subject; each shows due week (if scheduled in
  current term) + Colab.
- `tools.qmd` *(new)* — gallery from `generated/gallery.json` (standalone tools + lecture apps).

---

## Interactivity runtime — static now, live marimo later

**Now (shipped):** all widgets render as **static** artifacts — build-time precompute for finite
interactions, and **client-side WASM** (marimo + Pyodide) for continuous multi-control ones.
`build_interactives.py` exports every `.embed()` widget to a self-contained app under `apps/`. This
runs free on GitHub Pages, scales infinitely, and never rots — current term and archives alike.
Cold-load on the WASM widgets stays mitigated by the existing click-to-load.

**Forward-compat:** page generators emit each widget through a single generated embed snippet (one
`<iframe src>` indirection per app) instead of hand-wired iframes, so adding a live path later is a
localized swap, not a rewrite.

The **live marimo server** for the current term is a **future step** (see *Future steps*) — GitHub
Pages is static-only, so we ship static-first.

---

## Main page design

Navbar — **left**: Home · Schedule · Lectures · Assignments · Tools · Blog. **right**: a *Course*
dropdown (Syllabus · Archive · About) + GitHub icon.

- **Home (`index.qmd`)** — hero (title + tagline); a **generated current-term banner** (term,
  meeting time/place, instructor, key dates) injected from `offering.yml`; one featured live
  interactive (embedded PrivacyPlot); quick-link cards to Schedule / Lectures / Assignments / Tools;
  a short pointer for standalone visitors → Tools & Blog.
- **Schedule** — generated current-term week table (above).
- **Lectures** — catalog grouped by subject; each card: title, subjects, *self-study tutorial*,
  *presentation deck*, *Open in Colab*, and the interactive apps it contains.
- **Assignments** — grouped by subject; each: title, subjects, est. time, related lectures, due week
  (if in current offering), *Open in Colab*.
- **Tools** — gallery of standalone tools + lecture-embedded widgets; each a card with title, source
  provenance ("from Lecture N" or "standalone"), and open link.
- **Blog** — Quarto listing of posts (date, tags, summary); posts may embed widgets.
- **Syllabus** — topics, prerequisites, grading, policies, staff/office hours, logistics (logistics
  pulled from the current `offering.yml`).
- **Archive** — list of offerings → each term's schedule (inline collapsible).
- **About** (small) — libdpy, references, repo links.

---

## Key changes by component

### [2] Infrastructure (`scripts/`, `tests/`)
- `sync_lectures.py` → `sync_content.py`. Keep `discover_lectures()`; add `discover_assignments()`,
  `load_course()` (reads `content/course.yml`), `load_offerings()` (parse each `offering.yml` +
  `schedule.csv` via stdlib `csv`). Point roots at `content/`. Add generators for schedule /
  archive / lectures / assignments / tools and the home-page current-term banner, all reusing
  `_replace_generated_section` + the `BEGIN_MARKER`/`END_MARKER` pattern.
- `build_interactives.py`: scan `content/lectures/**`, `blog/**`, `tools/**` for `.embed()`; export
  each widget to static WASM; emit `generated/gallery.json` (name, title, source, path) for
  `tools.qmd`. Keep the generated marimo app sources in a stable dir (reused by the future live server).
- Page generators emit widgets via a single per-app embed snippet (forward-compat indirection for the
  future live path).
- `scripts/colab.py`: build `colab.research.google.com/github/<owner>/<repo>/blob/<branch>/<path>`
  from `content/course.yml`; page generators render badges from it.
- Update `tests/` for new paths; add tests for `schedule.csv` parsing, assignment discovery, and
  offering selection.

### [3] Content
- **Move** `lectures/` → `content/lectures/` (cheap now — 2 lectures). Add `content/course.yml`,
  `content/offerings/2026-fall/{offering.yml,schedule.csv}`, `content/assignments/`.
- Author `hypothesis-testing-hw` assignment (Colab-ready, first cell `!pip install libdpy`).
- Scaffold `blog/index.qmd` + one example post, and one example standalone `tools/<slug>/`.

### [1] Site shell + theme
- `_quarto.yml`: render globs → `content/lectures/**/*.qmd`, `content/lectures/**/learn.ipynb`,
  `content/assignments/**/*.ipynb`, `blog/**`, `tools/**`; `resources: content/lectures/**/apps/**`;
  navbar as above; add `blog/index.qmd` listing config. `theme: [cosmo, theme/custom.scss]` for an
  academic look (evaluate a known open-source Quarto course style; non-blocking).

### [4] Authoring kit
- `AUTHORING.md` (supersedes local `LECTURE_WORKFLOW.md`): add lecture / assignment / tool / post,
  edit `schedule.csv`, **start a new offering** (copy `offerings/<term>/`, set `current_offering`),
  subject tags, Colab notes. `templates/` skeletons + manifest stubs. Move `tutorials/slide-authoring/`.

### [5] Dev plan + tools
- Move durable planning/design docs into `dev/plan/` and **track** them (volatile `STATUS.md` stays
  ignored). `dev/tools/` holds the local render recipe script.

### `.gitignore`
- `/lectures/**/...` → `/content/lectures/**/...`; ignore `content/assignments/**/solution.ipynb`;
  ignore in-place render artifacts under `blog/`, `tools/`; un-ignore tracked `dev/plan/` docs.

---

## Migration order (site keeps building each step)

> **Progress (2026-06-22):** All migration phases (0–8) are complete. Follow-up polish added lecture
> app links on **Lectures**, a past offering (`2025-fall`) for **Archive**, instructors on Home,
> reading week in the current schedule, baseline route fixture, and removal of the `sync_lectures`
> wrapper. Lecture 02 transitional surfaces (`slides.qmd` stub, `status: planned`) remain for a
> later cleanup pass.

1. ~~Create `content/`, move `lectures/` → `content/lectures/`, add `course.yml`, first
   `offerings/<term>/` (config from current 2 lectures), empty `assignments/`. Update `_quarto.yml`,
   `sync_content.py`, `build_interactives.py`, `tests/`, `.gitignore`. Re-render (one full re-render
   — `_freeze` is path-keyed). Confirm lectures 2 & 3 + WASM apps still build.~~ ✓ (2026-06-21)
2. ~~Offering-driven `schedule.qmd` + `archive.qmd`~~ ✓ (2026-06-21); ~~Colab badges on lecture pages
   (Phase 4).~~ ✓ (2026-06-21)
3. ~~Add `hypothesis-testing-hw`; generate `assignments.qmd` by subject with due weeks.~~ ✓ (2026-06-21)
4. ~~Tools gallery: `gallery.json` from `build_interactives.py` → `tools.qmd`; scaffold one standalone
   `tools/<slug>/`.~~ ✓ (2026-06-21)
5. ~~`blog/` (listing + example post). Home-page current-term banner.~~ ✓ (2026-06-22; banner shipped in Phase 2)
6. ~~`authoring/` (move tutorial, write `AUTHORING.md`, templates), `dev/` (move plan docs).~~ ✓ (2026-06-22)
   ~~Restyle via `theme/custom.scss`.~~ ✓ (2026-06-22)

## Critical files
`_quarto.yml` · `scripts/sync_lectures.py`→`scripts/sync_content.py` · `scripts/build_interactives.py`
· `scripts/colab.py` (new) · `content/course.yml`, `content/offerings/<term>/{offering.yml,schedule.csv}` (new)
· `schedule.qmd`/`lectures.qmd` · `assignments.qmd`/`tools.qmd`/`archive.qmd` (new) ·
`blog/index.qmd` (new) · `content/lectures/*/manifest.yml` · `tests/run_smoke_tests.py` ·
`.gitignore` · `.github/workflows/publish.yml`.

---

## Verification

- **Local build**: `QUARTO_PYTHON=$(pwd)/.venv/bin/python MPLBACKEND=Agg ~/.local/quarto-1.6/bin/quarto render --execute` builds `_site/` with no path errors; lectures 2 & 3 + both PrivacyPlot WASM apps render.
- **Generated pages**: `schedule.html` reflects the current offering's `schedule.csv`; `archive.html`
  lists offerings; `assignments.html` groups by subject; `tools.html` lists every widget;
  `blog/index.html` lists posts; Colab badges open valid `colab.research.google.com/github/...` URLs
  (confirm `pip install libdpy` cell runs).
- **Offering switch**: change `current_offering` in `content/course.yml`; re-render; Home banner +
  Schedule update, the prior term appears under Archive.
- **Unit tests**: `pytest tests/` (existing + new schedule/assignment/offering tests) pass.
- **Smoke tests**: `python tests/run_smoke_tests.py` drives each WASM app in headless Chrome against
  the new `content/lectures` paths.
- **CI**: push a branch; `publish.yml` renders, runs unit + smoke tests, deploys to Pages.

## Assumptions / risks to confirm during build
- **libdpy Colab rendering**: `.embed()` targets WASM iframes; in Colab it must fall back to inline
  ipywidgets/Plotly — a `libdpy` (pub_lib) change, outside this repo, required for the Colab promise.
- **Live-rebuild archive**: past-term pages re-render from the current shared catalog, so later
  content edits flow into old terms (accepted). Freezing exact past sites would be a later add
  (git-tag → versioned subpath) if ever needed.
- **Theme**: pick the academic SCSS during step 6; cosmo stays the safe default.
- **Plan-doc tracking**: this tracks `dev/plan/` docs and keeps `STATUS.md` ignored — reverses the
  recent "stop tracking planning docs" choice; easy to flip.

---

## Future steps (not in the initial build)
- **Live marimo server for the current term.** Host a `marimo run` backend (always-on small instance,
  scale-to-zero serverless, or HF Spaces) and switch current-term embeds from WASM to the live URL,
  keeping WASM as the automatic fallback. Adds: a host choice, a CI deploy job for the current
  offering's apps, and `sync_content.py` routing of live-vs-WASM by the current-app set. The embed
  indirection (above) keeps this localized. Deferred because GitHub Pages is static-only.
- **Frozen past-offering snapshots** — only if content drift becomes a problem: build tagged years
  into versioned subpaths so archived sites are byte-exact.
- **Assignment auto-grading / timed solution release**, if wanted later.
