# Generated assets — do not hand-draw

Static fallback snapshots referenced by `slides.qmd` and `manifest.yml` are **generated** from
`notebook.ipynb` / the `apps/` widgets in CI (v4 §7), so they cannot drift from the live demo:

- `reconstruction-error-static.png` — from `#| label: fig-reconstruction-error`
- `slab-2d-static.png` — snapshot of `interactive_2d_slab`
- `slab-3d-static.png` — snapshot of `interactive_3d_slabs` / `plot_3d_out_of_cube_example`

These are produced once the render/CI step is wired (Phase 2, step 4); the `libdpy` modules they
depend on are already public.
