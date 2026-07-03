# Quarantined dev tools

Scripts here are **not** part of the website delivery path. They may be stale,
hand-maintained, or unsafe to run without review.

| Script | Reason quarantined |
|---|---|
| `sync_subgroup_lecture.py` | Stale Part II deck template (pre-`de82b22` API names), baked TheoryROC literals in blog generation, and not a deterministic `--check` gate. Do not run to regenerate committed artifacts until rewritten. |

Active lecture alignment for `private-subgroup-comparisons` is maintained manually against
`code_base_dev/lectures/migrated/lecture_private_subgroup_comparisons.ipynb` and the released
`libdpy` pin in `requirements.txt`.
