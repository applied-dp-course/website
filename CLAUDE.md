# Website guidance

This is the public Quarto site. It imports all computation from `libdpy` (installed from `pub_lib`)
and defines no course logic of its own. Rules live in public docs — read the relevant one first.
**Full instruction-file index** (all repos) → `../.cursor/rules/instruction-docs.mdc`.

- Content collections, templates, plotting policy (`.show()` vs `.embed()`), and validation →
  [authoring/AUTHORING.md](authoring/AUTHORING.md)
- Build/dev commands and layout → [README.md](README.md)
- **Developing/migrating a lecture** (workflow + preconditions) → *Developing a lecture* in
  [authoring/AUTHORING.md](authoring/AUTHORING.md); the libdpy release it depends on →
  [../code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md](../code_base_dev/DEVELOPMENT/PUB_LIB_DELIVERY.md)

Before adding or changing content or interactives, remember: the site pins `libdpy` to a tag in
`requirements.txt`, and `./dev/tools/render.sh` installs that pin. When content needs new libdpy
API, release and tag first, then bump the pin in the **same commit** as the content; do not
`pip install -e` local libdpy (it is reverted on render). Validate with `./dev/tools/render.sh`
**and** `./.venv/bin/python tests/run_smoke_tests.py`. A lecture is not shipped until *Delivery gate*
in [authoring/AUTHORING.md](authoring/AUTHORING.md) passes — infra-only green CI does not count.
