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
belong under `content/`. Generated interactives are written to `_generated/apps/`; authored
browser-native apps live under top-level `apps/`. Quarto may write execution results back into
notebooks while rendering; the first post-render hook removes them immediately.

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

## Validation

```bash
./.venv/bin/python scripts/content_model.py
./.venv/bin/python -m pytest tests -q
./dev/tools/render.sh
```

Validation rejects numbered content names, missing entrypoints, wrong source types, and offering
references that do not match an authored content name.

Private `solution.ipynb` files under class or home assignments are ignored and blocked from the
rendered site.
