# Applied Differential Privacy — public site mirror

> **Output mirror (Stage 2):** this repo holds **rendered site output only**. Author and edit
> content in the private monorepo
> [`code_base_dev`](https://github.com/applied-dp-course/code_base_dev) (`content/`, `pages/`,
> `authoring/`, …). Pushes to `main` here come from the monorepo **Publish site** workflow —
> do not edit files by hand.

The live course site is served at **https://applied-dp-course.github.io/website/**.

Computation is imported from [`libdpy`](https://github.com/applied-dp-course/pub_lib) (student pip
install path). Dev/CI builds use in-tree `libdpy` in `code_base_dev`.

## What belongs here

After each monorepo deploy, the repo root mirrors Quarto's `_site/` output: `pages/`, `content/`,
`_generated/`, etc. The only hand-maintained files are this README and
`.github/workflows/deploy-pages.yml`.

## Development

All authoring, validation, and delivery gates run in `code_base_dev`. See
[`authoring/AUTHORING.md`](https://github.com/applied-dp-course/code_base_dev/blob/main/authoring/AUTHORING.md)
in the monorepo.
