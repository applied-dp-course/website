# Website Status

Live status for the course website. Updated as phases land. See `PLAN.md` for the plan and
`applied-dp-course-website-plan.md` (git-ignored) for the v4 architecture rationale.

_Last updated: 2026-06-15_

## Snapshot

| Phase | State |
|---|---|
| Repo bootstrap (git + remote + `.gitignore`) | ✅ done |
| Plan + status authored | ✅ done |
| Phase 0 — runtime spike | ⬜ not started |
| Phase 1 — site shell | 🟡 scaffolded (config + lecture template stubs), not wired/deployed |
| Phase 2 — reconstruction lecture | 🟡 scaffolded (import-only); host path unblocked, WASM needs wheel |
| Phases 3–6 | ⬜ not started |

## Done

- Initialized git in `website/`, set `origin` → `github.com/applied-dp-course/website.git`,
  branch `main`.
- `.gitignore` committed; `applied-dp-course-website-plan.md` (v4) intentionally ignored.
- `PLAN.md` / `STATUS.md` authored — prime directive recorded (website = import-only).
- Scaffolded reconstruction lecture under `lectures/02-reconstruction/` (slides, notebook,
  manifest, app entrypoints, assets placeholder) — **import-only, no implementation**.

## Blockers

- **libdpy browser wheel (v4 §1.1):** no hosted `.whl` yet; `micropip`/`piplite` cannot install
  from `git+`. Required before any Tier-2 (WASM) element — including the slab apps — runs in the
  browser. Local/Colab/host render via the existing `git+` install is unaffected. Datasets are now
  bundled in the package (`pub_lib` commit `76152ae`); confirm they survive the **wheel** build,
  not just the source install.

_Resolved (was a false alarm):_ an earlier "PR-LIB-1" blocker claimed the reconstruction modules
were missing from public `pub_lib`. They are in fact on `origin/main` (commit `ec7527b`); the
local `pub_lib` checkout was 3 commits behind. No library PR is needed for the host path. **Lesson:
check the import surface against `origin/main`, not a possibly-stale local checkout.**

## Next actions

1. Sync the local `pub_lib` checkout to `origin/main` (it was 3 commits behind as of 2026-06-15).
2. Build + host the `libdpy` wheel; prove `micropip` install + packaged-CSV load (v4 §8 steps 1–2).
3. Run Phase 0 spike; gate on the core path (v4 §14).
4. Fill `notebook.ipynb` figure instance-builders and wire `slides.qmd` embeds.
5. Flip `manifest.yml` `status` to `migrated` only after §8 smoke tests pass on the deployed site.

## Verification log

| Date | What was verified | Result |
|---|---|---|
| 2026-06-15 | Reconstruction import surface vs. `pub_lib` `origin/main` | all modules PRESENT (commit `ec7527b`); local checkout 3 behind |
| 2026-06-15 | Datasets bundled in installed package | yes, `pub_lib` commit `76152ae` (source install; wheel TBD) |
| — | libdpy wheel installs via micropip + CSV loads in-browser | pending |
| — | slab apps render in Chrome/Firefox/Safari on deployed site | pending |
