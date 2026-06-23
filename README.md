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

Quarto runs catalog validation and page synchronization before rendering. Generated catalog and
interactive artifacts are written under `_generated/`; rendered pages are written under `_site/`.

See [authoring/AUTHORING.md](authoring/AUTHORING.md) for detailed workflows.
