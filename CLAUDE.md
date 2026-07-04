# Website guidance

**Agents: your operating rules are in [`../AGENTS.md`](../AGENTS.md)** (workspace root). This file is
human-developer reference for the website repo.

This is the public Quarto site. It imports all computation from `libdpy` (installed editable from
sibling `code_base_dev/libdpy` in dev/CI) and defines no course logic of its own. Rules live in
public docs — read the relevant one first.
**Full instruction-file index** (all repos) → `../.cursor/rules/instruction-docs.mdc`.

- Content collections, templates, plotting policy (`.show()` vs `.embed()`), and validation →
  [authoring/AUTHORING.md](authoring/AUTHORING.md)
- Build/dev commands and layout → [README.md](README.md)
- **Developing/migrating a lecture** (workflow + preconditions) → *Developing a lecture* in
  [authoring/AUTHORING.md](authoring/AUTHORING.md); student pip releases →
  [../code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md](../code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md)

Before adding or changing content or interactives: `./dev/tools/render.sh` runs `sync_libdpy.sh`
(in-tree libdpy). Implement new API in `code_base_dev/libdpy/` first — no `pub_lib` release needed
to render. Validate with `./dev/tools/render.sh` **and**
`./.venv/bin/python tests/run_smoke_tests.py`. A lecture is not shipped until *Delivery gate*
in [authoring/AUTHORING.md](authoring/AUTHORING.md) passes — infra-only green CI does not count.
