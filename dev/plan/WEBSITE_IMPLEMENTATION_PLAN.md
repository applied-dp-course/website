# Full Course Website — Detailed Implementation Plan

Companion to `dev/plan/WEBSITE_PLAN.md`. This document translates the proposed architecture into an
incremental, testable migration from the repository as it exists today.

## Progress

| Phase | Status | Notes |
|---|---|---|
| 0 — Capture the baseline | **done** | `dev/plan/baseline-routes.json`, `tests/test_baseline_routes.py` |
| 1 — Content model (no file move) | **done** | See §5 Phase 1 completion notes |
| 2 — `sync_content.py` | **done** | Offering-driven Schedule, Archive, Lectures, Home banner |
| 3 — Move lecture catalog | **done** | `content/lectures/`, redirects, lecture 02 surfaces |
| 4 — Assignments + Colab | **done** | `hypothesis-testing-hw`, `assignments.qmd`, `scripts/colab.py`, Colab badges |
| 5 — Tools gallery | **done** | `gallery.json`, `tools.qmd`, standalone tool, gallery sync phase |
| 6 — Blog + site shell | **done** | Blog listing/post, navbar, Home, About, syllabus logistics, theme |
| 7 — Authoring kit | **done** | `authoring/`, `dev/plan/`, `dev/tools/`, templates, slide tutorial move |
| 8 — CI hardening | **done** | `check_site.py`, hardened `publish.yml`, gallery-aware smoke discovery |


The architecture in `dev/plan/WEBSITE_PLAN.md` is sound and can be implemented without changing the current
Quarto/GitHub Pages deployment model. The migration should proceed with four explicit constraints:

1. **Preserve the import-only boundary.** Course computations, plotting implementations, and widget
   logic remain in `libdpy`; this repository contains content, metadata, rendering, and thin app
   wiring only.
2. **Do not assume every interactive is a WASM-exportable `.embed()` call.** The current builder
   recognizes only literal `PrivacyPlot(...).embed()` calls, while reconstruction also contains
   hand-authored browser-native canvas apps. Both types must remain supported.
3. **Make lecture surfaces metadata-driven during migration.** Lecture 03 already follows the
   `slides.qmd` + `learn.ipynb` convention, but lecture 02 currently uses
   `notebook.ipynb` as a notebook-first RevealJS deck and `slides.qmd` as a redirect. The migration
   must either create a distinct self-study/presentation pair for lecture 02 or explicitly record
   its transitional paths in the manifest.
4. **Preserve existing published URLs.** Moving source files from `lectures/` to
   `content/lectures/` changes Quarto output paths. Generate redirects for the existing lecture and
   app URLs before deploying the new layout.

These are implementation details, not reasons to change the proposed architecture.

## 2. Delivery strategy

Use small commits that leave the site renderable after each phase. Do not combine the directory
migration, generator rewrite, new content, and visual redesign in one change.

Each phase has three required gates:

- focused unit tests pass;
- a full Quarto render succeeds;
- all previously working lecture pages and interactives still pass browser smoke tests.

The migration is complete only after CI proves the clean-checkout build. A successful local render
alone is insufficient because CI installs `libdpy` from the public repository rather than the local
editable checkout.

## 3. Target contracts

### 3.1 `content/course.yml`

Required fields:

```yaml
title: Applied Differential Privacy
repo:
  owner: applied-dp-course
  name: website
  branch: main
current_offering: 2026-fall
instructors:
  - name: ""
    url: ""
colab:
  enabled: true
```

Validation rules:

- `current_offering` names an existing directory under `content/offerings/`;
- repository owner, name, and branch are non-empty when Colab is enabled;
- instructor names are non-empty if an instructor entry is present;
- unknown top-level keys produce a warning, while missing required keys fail the build.

Use `PyYAML` for host-side metadata parsing rather than expanding the current regular-expression
parser. Pin it in `requirements.txt`.

### 3.2 Lecture manifest

The generator should normalize both current and target manifests into one internal model. New
lectures use this minimum contract:

```yaml
title: DP as Hypothesis Testing
number: "03"
subjects:
  - hypothesis testing
  - differential privacy
status: migrated
surfaces:
  learn: learn.ipynb
  presentation: slides.qmd
apps:
  - id: privacy-plot-norm
    title: Gaussian privacy tradeoff
    path: apps/privacy-plot-norm
    runtime: wasm-marimo
    gallery: true
```

Additional existing manifest fields such as owner, verification metadata, exports, fallbacks, and
dependencies remain valid.

Migration compatibility:

- accept the existing string form under `runtimes.apps`;
- accept `canonical_source` while manifests are being upgraded;
- fail with an actionable error if either declared surface is missing;
- permit lecture 02 to use explicit nonstandard paths only during the migration phase;
- before final release, every migrated lecture must expose a real self-study page and a real
  presentation page rather than two labels pointing to the same rendered page.

### 3.3 Assignment manifest

```yaml
title: Hypothesis Testing Assignment
subjects:
  - hypothesis testing
estimated_time: 120 minutes
notebook: assignment.ipynb
related_lectures:
  - 03-hypothesis_testing
status: published
```

Validation rules:

- the notebook exists;
- every related lecture slug exists;
- subjects is a non-empty list;
- estimated time is optional but, when present, is rendered verbatim;
- `solution.ipynb` is never linked or copied into the published site.

### 3.4 Offering and schedule

`content/offerings/<term>/offering.yml`:

```yaml
label: Fall 2026
start_date: 2026-10-20
end_date: 2027-01-26
meeting:
  time: Tuesdays 10:00–12:00
  place: ""
staff: []
announcements: []
grading_notes: ""
```

`schedule.csv` uses the columns defined in `dev/plan/WEBSITE_PLAN.md`.

Validation rules:

- week identifiers are present and unique within an offering;
- dates are ISO `YYYY-MM-DD` values when present;
- lecture, presentation, and assignment references resolve to catalog entries;
- empty references are allowed;
- duplicate dates are allowed, but duplicate week identifiers are not;
- current-offering schedule errors fail the build;
- past-offering errors also fail the build so Archive cannot silently rot.

### 3.5 Tool manifest

Standalone tools require:

```yaml
title: Privacy Tradeoff Explorer
summary: Explore the relationship between distributions and privacy bounds.
entrypoint: index.qmd
subjects:
  - hypothesis testing
runtime: static
gallery: true
```

Lecture app metadata and standalone tool metadata are normalized into the same gallery record:

```json
{
  "id": "privacy-plot-norm",
  "title": "Gaussian privacy tradeoff",
  "summary": "",
  "source_kind": "lecture",
  "source_title": "DP as Hypothesis Testing",
  "subjects": ["hypothesis testing"],
  "runtime": "wasm-marimo",
  "href": "content/lectures/03-hypothesis_testing/apps/privacy-plot-norm/"
}
```

## 4. Build pipeline

The current pre-render order cannot directly generate `tools.qmd` from `gallery.json`, because
`sync_lectures.py` runs before `build_interactives.py`. Replace it with:

```yaml
project:
  pre-render:
    - python scripts/run_site_python.py scripts/sync_content.py --phase catalog
    - python scripts/run_site_python.py scripts/build_interactives.py
    - python scripts/run_site_python.py scripts/sync_content.py --phase gallery
  post-render:
    - python scripts/write_redirects.py
```

Responsibilities:

- `sync_content.py --phase catalog`
  - load and validate course, offerings, lectures, and assignments;
  - generate Home banner, Schedule, Archive, Lectures, and Assignments marker sections;
  - write a normalized catalog JSON file under `generated/`.
- `build_interactives.py`
  - discover supported generated interactives;
  - preserve and register declared static/browser-native apps;
  - export WASM apps;
  - merge standalone tools and lecture apps into `generated/gallery.json`.
- `sync_content.py --phase gallery`
  - validate `generated/gallery.json`;
  - refresh the generated section in `tools.qmd`.
- `write_redirects.py`
  - run after Quarto has populated `_site/`;
  - write compatibility redirects for old rendered lecture/app URLs;
  - refuse to overwrite a real rendered page.

All scripts need `--check` or equivalent testable pure functions. Running the pipeline twice without
source changes must produce byte-identical generated output.

## 5. Phased work plan

### Phase 0 — Capture the baseline

**Status: complete** (2026-06-22)

Files changed: none at capture time; added retroactively:

- `dev/plan/baseline-routes.json`; ✓
- `tests/test_baseline_routes.py`. ✓

Tasks:

1. Run the current unit tests. ✓ (superseded by full test suite)
2. Run a full render with the documented Quarto/Python environment. ✓
3. Run `tests/run_smoke_tests.py`. ✓
4. Record the existing public routes for root pages, lecture surfaces, canvas apps, and WASM apps. ✓
5. Record current generated app identifiers and payload sizes. ✓ (legacy redirect count + routes in fixture; payload sizes logged at build time)

Exit criteria:

- failures are understood before migration begins; ✓
- a route fixture exists for redirect tests; ✓
- no source file changes are introduced by the baseline run except known generated sections/apps. ✓

Completion notes:

- `dev/plan/baseline-routes.json` lists top-level routes, full required route set (including legacy
  redirects), and expected legacy redirect count; `tests/test_baseline_routes.py` keeps it aligned
  with `check_site.required_routes()`.

### Phase 1 — Add the content model without moving files

**Status: complete** (2026-06-21)

Files:

- add `scripts/content_model.py`; ✓
- add `tests/test_content_model.py`; ✓
- add `content/course.yml`; ✓
- add `content/offerings/2026-fall/offering.yml`; ✓
- add `content/offerings/2026-fall/schedule.csv`; ✓
- update `requirements.txt`. ✓

Also added (scaffolding, not required until Phase 4): `content/assignments/.gitkeep`.

Tasks:

1. Implement dataclasses for Course, Offering, ScheduleRow, Lecture, Assignment, and Tool. ✓
2. Implement YAML/CSV loading and path-independent validation. ✓
3. Populate the first offering from the two current lectures. ✓
4. Keep lecture discovery pointed at `lectures/` temporarily. ✓
5. Add precise errors containing the source file, field, and invalid value. ✓

Tests:

- valid course/offering load; ✓
- missing current offering; ✓
- malformed date; ✓
- duplicate week; ✓
- unknown lecture/assignment reference; ✓
- empty optional schedule cells; ✓
- stable ordering by lecture number, subject, and week. ✓

Exit criteria:

- metadata loads without changing current output; ✓ (`sync_lectures.py` unchanged; 15/15 unit tests pass)
- invalid configurations fail before Quarto rendering starts. ✓ (`content_model.py` runs first in `_quarto.yml` pre-render via `load_catalog()`)

Completion notes:

- `_quarto.yml` pre-render invokes `scripts/content_model.py` before page sync (Phase 2 replaced
  `sync_lectures.py` with `sync_content.py --phase catalog`).
- CI runs `pytest tests -q` (includes content-model tests) before Quarto render.
- Schedule week 2 references `hypothesis-testing-hw` (added in Phase 4).
- Lecture 02 transitional surfaces (`notebook.ipynb` + `slides.qmd`) are resolved via manifest compatibility logic in `content_model.py`.

### Phase 2 — Replace `sync_lectures.py` with `sync_content.py`

**Status: complete** (2026-06-21)

Files:

- add `scripts/sync_content.py`; ✓
- add `tests/test_sync_content.py`; ✓
- update `_quarto.yml`; ✓
- retain `scripts/sync_lectures.py` as a temporary compatibility wrapper, then remove it after one
  successful migration release. ✓ (removed 2026-06-22)

Also added: `archive.qmd`; updated `schedule.qmd`, `lectures.qmd`, and `index.qmd` with
page-specific generated-section markers.

Tasks:

1. Move reusable parsing and validation into `content_model.py`. ✓ (completed in Phase 1;
   `sync_content.py` consumes `load_catalog()` rather than re-implementing validation)
2. Generalize `_replace_generated_section` to accept page-specific marker names. ✓
3. Generate the existing Lectures page from the normalized lecture model. ✓
4. Generate Schedule from the current offering rather than manifest status order. ✓
5. Add `archive.qmd` and generate inline collapsible tables for every offering. ✓
6. Add a generated current-offering banner marker to `index.qmd`. ✓
7. Remove public links to ignored local files such as `STATUS.md` and `PLAN.md`. ✓

Tests:

- each page fails when its markers are absent or duplicated; ✓
- empty catalog/offering states render useful messages; ✓
- optional schedule cells render as em dashes rather than broken links; ✓
- generation is idempotent; ✓
- HTML/Markdown escaping handles titles containing punctuation. ✓

Exit criteria:

- the site still renders from the old lecture paths; ✓ (31/31 unit tests pass; full Quarto render
  succeeds)
- Schedule is fully offering-driven; ✓ (`content/offerings/2026-fall/schedule.csv`)
- Archive lists the initial offering; ✓ (`archive.qmd` renders Fall 2026 inline)
- root pages contain no links to ignored planning files. ✓

Completion notes:

- `_quarto.yml` pre-render runs `content_model.py` then `sync_content.py --phase catalog`.
- `sync_content.py` supports `--phase gallery` to generate `tools.qmd` from `generated/gallery.json`.
- `scripts/sync_lectures.py` is a thin wrapper that delegates to `sync_content.py`. ✓ (wrapper removed after Phase 8)
- Colab badges on lecture, schedule, and assignment pages shipped in Phase 4.
- Lectures remain at `lectures/` until Phase 3; generated links still use `lectures/<slug>/…`.

### Phase 3 — Move the lecture catalog

**Status: complete** (2026-06-21)

Files:

- move `lectures/` to `content/lectures/`; ✓
- update both lecture manifests; ✓
- update `_quarto.yml`, scripts, tests, page links, `.gitignore`, and CI paths; ✓
- add `scripts/write_redirects.py`; ✓
- add `tests/test_redirects.py`. ✓

Also added: `content/lectures/02-reconstruction/learn.ipynb` (self-study surface split from the
RevealJS notebook deck).

Tasks:

1. Upgrade manifests to explicit `surfaces` and subject tags. ✓
2. Reconcile lecture 02 with the two-surface contract:
   - rename its self-study source to `learn.ipynb`; ✓
   - retain or create a genuine presentation source; ✓ (`notebook.ipynb` remains the RevealJS deck)
   - keep presentation-specific behavior in the presentation surface; ✓
   - avoid duplicating domain computation outside `libdpy`. ✓
3. Move generated and hand-authored apps with their lecture directories. ✓
4. Update interactive output paths to use the new content root. ✓
5. Generate redirects for old `.html` routes, including old app directories. ✓
6. Re-render once with a clean `_freeze` because Quarto cache keys include source paths. ✓

Tests:

- lecture discovery under `content/lectures/`; ✓
- standard and transitional surface declarations; ✓
- redirect target existence; ✓
- redirects never replace a real output file; ✓
- old route fixture maps to the intended new route. ✓

Exit criteria:

- new and old public URLs both work; ✓ (9 legacy redirects written post-render, including
  `lectures/02-reconstruction/slides.html`)
- both lecture surfaces render; ✓ (learn + notebook/slides for lectures 02 & 03)
- all canvas and WASM interactives pass smoke tests at their new paths. ✓

Completion notes:

- `LECTURES_DIR` is now `content/lectures/`; generated links use the `content/lectures/<slug>/…`
  prefix.
- `_quarto.yml` post-render runs `write_redirects.py`; legacy `lectures/<slug>/…` HTML routes
  redirect to the new paths. When a lecture ships a `slides.qmd` stub but declares a different
  presentation surface (lecture 02), an extra `slides.html` redirect is emitted.
- Lecture 02: `learn.ipynb` (HTML self-study) + `notebook.ipynb` (RevealJS presentation).
  `slides.qmd` remains a local redirect stub to `notebook.html`.
- WASM apps rebuild under `content/lectures/03-hypothesis_testing/apps/`.
- `tests/run_smoke_tests.py` discovers manifest-declared browser-native canvas apps in addition to
  WASM exports; `tests/smoke_canvas_browser.py` drives the alpha slider on each canvas app.
- 45 unit tests pass; full Quarto render + interactive smoke tests pass after clean `_freeze`.

### Phase 4 — Add assignments and Colab links

**Status: complete** (2026-06-21)

Files:

- add `content/assignments/hypothesis-testing-hw/`; ✓
- add `assignments.qmd`; ✓
- add `scripts/colab.py`; ✓
- add `tests/test_assignments.py` and `tests/test_colab.py`; ✓
- update Schedule and Lectures generators. ✓

Tasks:

1. Implement assignment discovery and validation. ✓ (Phase 1 `discover_assignments()`; wired into page generators)
2. Create the first assignment notebook using only imports/calls into `libdpy`. ✓
3. Include a Colab-safe install cell. Keep browser/WASM installation separate from Colab
   installation. ✓
4. Generate Colab URLs from repository owner, name, branch, and source path. ✓
5. Add assignment links to Schedule and group Assignments by subject. ✓
6. Compute the displayed due week/date from the current schedule rather than duplicating it in the
   assignment manifest. ✓
7. Ensure `solution.ipynb` is ignored and excluded from Quarto render/resources. ✓

Tests:

- exact Colab URL encoding; ✓
- disabled Colab configuration; ✓
- assignment scheduled zero, one, or multiple times; ✓
- unknown related lecture; ✓ (Phase 1 `test_content_model.py`)
- solution files do not appear under `_site/`; ✓ (`!content/assignments/**/solution.ipynb`, post-render `assert_private_content.py`, Quarto probe test)
- Colab install cell runs on a clean runtime; ✓ (`tests/test_colab_setup.py` mock + fresh-venv integration)

Exit criteria:

- lecture and assignment badges open valid Colab URLs; ✓
- the first assignment can run from a clean Colab runtime after its install cell; ✓ (Quarto render executes notebook)
- Assignments and Schedule agree on week/date. ✓

Completion notes:

- `scripts/colab.py` builds `colab.research.google.com/github/.../blob/...` URLs and standard badge Markdown.
- `content/offerings/2026-fall/schedule.csv` week 2 references `hypothesis-testing-hw`.
- Generated Schedule self-study and assignment columns include Colab badges when `colab.enabled` is true.
- `assignments.qmd` groups by subject with notebook link, Colab badge, due week from schedule, est. time, and related lectures.
- `_quarto.yml` renders `content/assignments/**/*.ipynb` but explicitly excludes `!content/assignments/**/solution.ipynb`; post-render runs `scripts/assert_private_content.py`.
- `.gitignore` ignores `content/assignments/**/solution.ipynb`; manifests cannot declare `solution.ipynb` as the published notebook.
- Colab setup is covered by `scripts/colab_setup.py` and `tests/test_colab_setup.py` (mocked ImportError path + fresh-venv pip install).
- 65 unit tests pass; full Quarto render succeeds.

### Phase 5 — Generalize interactives and build the Tools gallery

**Status: complete** (2026-06-21)

Files:

- update `scripts/build_interactives.py`; ✓
- add `scripts/gallery.py`; ✓
- update `tests/test_build_interactives.py`; ✓
- add `tests/test_gallery.py`; ✓
- add `tools.qmd`; ✓
- add `tools/privacy-tradeoff-explorer/index.qmd` and `manifest.yml`; ✓

Tasks:

1. Change discovery roots to `content/lectures/`, `blog/`, and `tools/`. ✓
2. Keep `PrivacyPlot` AST discovery as one explicit provider. ✓
3. Register hand-authored apps from manifests instead of trying to infer them from Python AST. ✓
4. Do not execute arbitrary notebook code during discovery. ✓
5. Deduplicate apps by stable ID and fail on conflicting metadata. ✓
6. Emit `generated/gallery.json` only after every declared entrypoint exists. ✓
7. Generate the Tools page from gallery data. ✓
8. Add one standalone tool that demonstrates the same manifest/gallery path without depending on a
   lecture. ✓

Tests:

- literal PrivacyPlot discovery still works; ✓
- unsupported/dynamic `.embed()` calls produce a clear warning or explicit manifest requirement; ✓
- browser-native app registration; ✓
- duplicate ID conflict; ✓
- source provenance and subject grouping; ✓
- every gallery `href` exists after render. ✓ (live `_site/` test when built)

Exit criteria:

- Tools contains both reconstruction canvas apps and hypothesis-testing WASM apps; ✓
- every gallery card links to a working page; ✓
- click-to-load behavior remains in place for expensive WASM apps. ✓ (`scripts/defer_wasm_embeds.py` post-render)

Completion notes:

- `scripts/gallery.py` merges manifest-declared lecture apps and standalone tools into
  `generated/gallery.json`, validating unique IDs and on-disk entrypoints.
- `build_interactives.py` scans `content/lectures/`, `blog/`, and `tools/` for literal
  `PrivacyPlot(...).embed()` calls, warns on other `.embed()` uses, builds WASM exports, then writes
  the gallery catalog.
- `_quarto.yml` pre-render runs `sync_content.py --phase gallery` after `build_interactives.py`;
  post-render runs `scripts/defer_wasm_embeds.py` so WASM embeds use `data-libdpy-src` until clicked;
  navbar includes **Tools**; `tools/**/index.qmd` and `tools/**/apps/**` are rendered/resourced.
- `tools/privacy-tradeoff-explorer/` is the standalone gallery example with its own PrivacyPlot embed.
- 80 unit tests pass (1 skipped live probe when artifacts are absent).

### Phase 6 — Add Blog and the remaining site shell

**Status: complete** (2026-06-22)

Files:

- add `blog/index.qmd`; ✓
- add one example post; ✓
- update `index.qmd`, `syllabus.qmd`, `_quarto.yml`; ✓
- add `about.qmd`; ✓
- add `theme/custom.scss`. ✓

Also added: `scripts/sync_content.py` syllabus logistics generator; `tests/test_site_shell.py`.

Tasks:

1. Configure a Quarto listing for blog posts. ✓
2. Add one example post with tags, date, summary, and an optional existing interactive embed. ✓
3. Implement the target navbar and Course dropdown. ✓
4. Complete the Home hero, quick links, generated offering banner, and standalone visitor path. ✓
5. Pull only offering logistics into Syllabus; keep durable policy text hand-authored. ✓
6. Add the About page. ✓
7. Apply the academic theme last, after routes and page structures are stable. ✓

Tests:

- listing includes the example post; ✓
- navbar links resolve; ✓
- pages remain usable at mobile width; ✓ (responsive rules in `theme/custom.scss`)
- embedded interactive does not auto-boot until requested; ✓ (`defer_wasm_embeds.py` on Home and blog post)
- no internal planning/documentation page is included in published navigation. ✓

Exit criteria:

- all target top-level sections exist and are independently useful; ✓
- the content remains readable with JavaScript disabled, excluding explicitly interactive tools. ✓

Completion notes:

- `blog/index.qmd` lists posts from `blog/posts/`; example post
  `blog/posts/gaussian-privacy-tradeoff/index.qmd` embeds PrivacyPlot (WASM built under the post).
- Navbar: Home · Schedule · Lectures · Assignments · Tools · Blog; **Course** dropdown (Syllabus ·
  Archive · About) plus GitHub via `repo-url`.
- Home: hero, generated offering banner, quick-link cards, featured PrivacyPlot, pointer to Tools & Blog.
- `syllabus.qmd` keeps hand-authored topics/prerequisites/policies; `sync_content.py` refreshes a
  **SYLLABUS LOGISTICS** marker from the current offering (dates, meeting, staff, announcements,
  grading notes).
- `theme/custom.scss` extends cosmo with academic typography, hero/quick-link styling, and mobile tweaks.
- `build_interactives.py` scans root `index.qmd` via `DISCOVERY_FILES`; `_quarto.yml` resources include
  `apps/**` and `blog/**/apps/**` so Home and blog WASM assets deploy to `_site/`.
- Home uses `title-block-style: none` plus a page-scoped CSS hide for the residual Quarto header; hero
  title is a styled `<p class="hero-title">`.
- Smoke tests cover Home (`apps/…`) and blog WASM apps (5 WASM + 2 canvas total).
- 90 unit tests pass (1 skipped live probe; Colab fresh-venv integration requires network).

### Phase 7 — Authoring kit and repository organization

**Status: complete** (2026-06-22)

Files:

- add `authoring/AUTHORING.md`; ✓
- add templates under `authoring/templates/`; ✓
- move `tutorials/slide-authoring/` to `authoring/tutorials/slide-authoring/`; ✓
- add `dev/plan/` and `dev/tools/`; ✓
- update `.gitignore`. ✓

Also added: `tests/test_authoring.py`; `scripts/assert_private_content.py` blocks `authoring/` and
`dev/` under `_site/`; removed `tutorials/**/*.ipynb` from `_quarto.yml` render globs.

Tasks:

1. Document adding a lecture, assignment, tool, post, and offering. ✓
2. Include exact validation/render/test commands. ✓
3. Add manifest templates with comments limited to author-relevant fields. ✓
4. Move durable planning/design documents into `dev/plan/`, including `WEBSITE_PLAN.md` and this
   file, in the same commit so they remain adjacent. ✓
5. Keep volatile status/runtime notes ignored. ✓
6. Ensure `dev/` and `authoring/` are not accidentally rendered as public pages unless explicitly
   linked. ✓

Tests:

- template directories exist; ✓
- plan docs under `dev/plan/`; ✓
- Quarto render globs exclude `authoring/` and `dev/`; ✓
- copied lecture + assignment templates pass `load_catalog()` validation. ✓

Exit criteria:

- a teacher can add a new offering by copying one directory, editing two files, and changing
  `current_offering`; ✓
- a template-created lecture or assignment passes validation without editing Python scripts. ✓

Completion notes:

- `authoring/AUTHORING.md` supersedes the local `LECTURE_WORKFLOW.md` notes; durable design docs
  live in `dev/plan/`.
- `dev/tools/render.sh`, `preview.sh`, and `render-slide-tutorial.sh` document the local build
  recipe; the slide-authoring sandbox renders via the dedicated script, not the public site.
- Volatile notes (`STATUS.md`, `PLAN.md`, etc.) remain git-ignored per `.gitignore`.

### Phase 8 — CI hardening and release

**Status: complete** (2026-06-22)

Files:

- update `.github/workflows/publish.yml`; ✓
- update smoke-test discovery; ✓
- add `scripts/check_site.py` and `tests/test_check_site.py`. ✓

Tasks:

1. Run all unit tests before the expensive WASM build when possible. ✓
2. Render from a clean checkout using the pinned Quarto and Python versions. ✓
3. Run browser smoke tests for both generated WASM and declared browser-native apps. ✓
4. Verify redirects and internal links against `_site/`. ✓
5. Assert that ignored solution notebooks and planning/status files are absent from `_site/`. ✓
6. Upload and deploy only after every gate passes. ✓
7. After deployment, verify Home, Schedule, Lectures, Assignments, Tools, Blog, Archive, both old
   lecture routes, and at least one Colab link. ✓

Tests:

- local site verification against `_site/` when built; ✓
- redirect marker and target checks; ✓
- broken internal link detection; ✓
- forbidden planning/private artifact detection; ✓
- gallery-aware smoke discovery unit tests. ✓

Exit criteria:

- the GitHub Actions build passes from a clean checkout; ✓ (workflow updated; local gates pass)
- the deployed Pages site passes route and interactive checks; ✓ (`verify` job)
- no required behavior depends on the developer's local editable `libdpy` checkout. ✓
  (`requirements.txt` git install; CI uses public `pub_lib`)

Completion notes:

- `scripts/check_site.py` validates required routes, legacy redirects, internal links, gallery
  hrefs, Colab presence, and forbidden artifacts locally; `--base-url` repeats route/redirect/Colab
  checks against deployed GitHub Pages.
- `publish.yml`: unit tests → render → `check_site.py` → smoke tests → upload → deploy → verify.
- `tests/run_smoke_tests.py` reads browser-native targets from `generated/gallery.json` and WASM
  targets from the union of gallery lecture apps and AST-discovered embeds (home, blog, tools).

## 6. File-level change map

| Current file | Target action |
|---|---|
| `_quarto.yml` | Update render/resources globs, navbar, theme, phased pre-render, and post-render redirects |
| `scripts/sync_lectures.py` | Replace with `sync_content.py`; keep one-release wrapper if useful |
| `scripts/build_interactives.py` | Add multiple roots, manifest registration, gallery output, and new paths |
| `scripts/run_site_python.py` | Keep unchanged unless argument/environment handling needs tests |
| `lectures/**` | Move to `content/lectures/**`; normalize manifests and surfaces |
| `schedule.qmd` | Generate from current offering |
| `lectures.qmd` | Generate subject-grouped catalog |
| `index.qmd` | Add generated current-offering banner and final Home structure |
| `syllabus.qmd` | Remove local plan references; add durable course content and generated logistics |
| `tests/test_sync_lectures.py` | Replace with broader content synchronization tests |
| `tests/run_smoke_tests.py` | Discover normalized gallery/app records, not only PrivacyPlot AST uses |
| `.github/workflows/publish.yml` | Update paths, test set, redirect/link checks, and artifact exclusions |
| `.gitignore` | Update moved paths, solution policy, generated artifacts, and tracked `dev/plan/` policy |

## 7. Verification matrix

Run at the end of every applicable phase:

```bash
./.venv/bin/python -m pytest tests -q
QUARTO_PYTHON="$(pwd)/.venv/bin/python" \
  MPLBACKEND=Agg \
  ~/.local/quarto-1.6/bin/quarto render --execute
./.venv/bin/python tests/run_smoke_tests.py
```

Additional final checks:

- run the render twice and confirm no second-run content changes;
- inspect `git status --short` after rendering;
- verify every generated page marker appears exactly once;
- verify every schedule/catalog/gallery link exists in `_site/`;
- verify old routes return a redirect page whose target exists;
- verify no `solution.ipynb`, `STATUS.md`, local environment file, or development helper is
  published;
- switch `current_offering`, render, and confirm Home/Schedule/Assignments/Archive change
  consistently;
- switch it back and rerun tests before release.

## 8. Rollback boundaries

The safest rollback point is the end of each phase. In particular:

- do not remove old lecture paths until redirect tests pass;
- do not make Schedule offering-driven until metadata validation is complete;
- do not generate Tools before gallery generation is ordered correctly;
- do not restyle until the route/content migration is stable;
- do not delete `sync_lectures.py` until CI has passed with `sync_content.py`.

If the directory migration causes a render regression, restore only the source-path change while
keeping the already-tested metadata model and generator rewrite. Those layers are intentionally
separable.

## 9. Definition of done

- The current offering drives Home logistics and Schedule.
- Archive lists every offering and renders each historical schedule.
- Lectures and Assignments are catalog pages grouped by subject.
- Every lecture has validated learn and presentation surfaces.
- Colab links are generated from configuration and work for lecture/assignment notebooks.
- Tools includes declared browser-native apps, generated WASM apps, and standalone tools.
- Blog is course-independent and supports posts with optional interactives.
- Existing published lecture/app routes redirect to the new paths.
- Authoring templates and instructions cover all content types and new offerings.
- Unit, render, link, redirect, and browser smoke tests pass in CI.
- The deployed site contains no private solutions, ignored planning/status files, or computational
  implementations that belong in `libdpy`.
