# Applied Differential Privacy course site

This Quarto site publishes lecture presentations, self-learning blog posts, assignments, and
interactive tools. Computation is imported from
[`libdpy`](https://github.com/applied-dp-course/pub_lib).

## Author-facing layout

```text
pages/                         hand-written site pages
content/
  lecture-presentations/      QMD RevealJS decks
  blog-posts/                  self-learning notebooks (course catalog)
  site-posts/                  editorial blog posts (Quarto pages)
  tools/                       standalone interactive tools
  class-assignments/           in-class notebooks
  home-assignments/            homework notebooks (currently empty)
  offerings/<term>/            offering metadata and schedule.csv
  course.yml                   selects the current offering
authoring/templates/           templates for source content
_generated/                     build output; never edit or commit
```

Every content item lives in an unnumbered, lowercase kebab-case directory such as
`hypothesis-testing`. Its hand-written `manifest.yml` names the entrypoint and presentation
metadata. Build scripts validate these files but never create, rename, or modify anything under
`content/`.

An offering only selects content. Its `schedule.csv` columns are:

```text
week,date,topic,blog_post,lecture_presentation,class_assignment,home_assignment,notes
```

The four content columns reference directory names, not sequence numbers or paths.

## Development

```bash
./.venv/bin/python scripts/content_model.py
./.venv/bin/python -m pytest tests -q
./dev/tools/render.sh
./.venv/bin/python tests/run_smoke_tests.py
```

CI runs the pytest line **before** Quarto render (see [authoring/AUTHORING.md](authoring/AUTHORING.md)
→ *Validation*). When adding content, update `dev/plan/baseline-routes.json` and
`tests/test_content_model.py` in the same commit.

**Shipping a lecture:** run `./dev/tools/deliver_lecture.sh --slug <slug>` — a fail-closed gate that
resolves libdpy imports on the pin, renders, checks routes, and smoke-tests; add `--push` to push and
block on a green CI build+deploy. See [authoring/AUTHORING.md](authoring/AUTHORING.md) → *Delivery
gate* (including *Common delivery pitfalls*). A local render passing, or a `pub_lib` tag existing, is
**not** "shipped".

Quarto runs catalog validation and page synchronization before rendering. Generated catalog and
interactive artifacts are written under `_generated/`; rendered pages are written under `_site/`.

### Fast iteration

The four commands above are the full gate. For single-lecture work, skip the site-wide render +
smoke and rebuild only what changed (full loop, and when a complete `render.sh` is still required:
[authoring/AUTHORING.md](authoring/AUTHORING.md) → *Validation*):

```bash
./.venv/bin/python scripts/build_interactives.py      # rebuild WASM apps only
quarto render content/blog-posts/<slug>/post.ipynb    # render one notebook
./.venv/bin/python tests/run_smoke_tests.py --slug <slug>
```

- **Pre-release libdpy checks:** `LIBDPY_SYNC=0 ./dev/tools/render.sh` renders against the currently
  installed env instead of installing the pinned libdpy from `requirements.txt` (also noted in AUTHORING).
- **PR smoke gate:** pull requests run scoped, blocking WASM smoke tests for changed lecture slugs.
  The full suite runs nightly (`smoke-nightly.yml`) across four parallel shards after a single
  render. **Require the PR build-check job via branch protection** — direct pushes to `main`
  deploy without smoke.
- **CI render cache:** GitHub Actions restores `_freeze/` and `_generated/` from a prior run.
  Cache keys are scoped to the libdpy pin; partial restores never cross pins. Within a job,
  `build_interactives.py` skips unchanged WASM apps. Full-site `quarto render --execute` respects
  project `freeze: auto` (only re-executes notebooks whose source changed); `--execute` is the
  default and does not override freeze on a global project render.

See [authoring/AUTHORING.md](authoring/AUTHORING.md) for detailed workflows.
