#!/usr/bin/env python3
"""Sync private-subgroup-comparisons website artifacts from the dev notebook."""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_NB = ROOT.parent / "code_base_dev/lectures/migrated/lecture_private_subgroup_comparisons.ipynb"
BLOG = ROOT / "content/blog-posts/private-subgroup-comparisons/post.ipynb"
DECK = ROOT / "content/lecture-presentations/private-subgroup-comparisons/presentation.qmd"

# Baked TheoryROC literals (recompute when DEFAULT_SEED / budgets change).
BAKED = {
    "global": {
        "loc_negative": 0.6183934157149957,
        "loc_positive": 0.6106134406021159,
        "scale": 15.894319728207908,
        "scale_negative": 15.894319728207908,
        "scale_positive": 15.894319728207908,
        "delta": 0.01,
        "compute_epsilon": True,
        "show_governing_point": True,
    },
    "typical_oracle": {
        "loc_negative": 0.6183934157149957,
        "loc_positive": 0.6106134406021159,
        "scale": 0.014609825128944782,
        "scale_negative": 0.014609825128944782,
        "scale_positive": 0.014609825128944782,
        "delta": 0.01,
        "bound_epsilon": 1.0,
        "show_governing_point": False,
    },
    "sparse_oracle": {
        "loc_negative": -1.3266757601823869,
        "loc_positive": 0.34117503892853895,
        "scale": 5.108888484066827,
        "scale_negative": 5.108888484066827,
        "scale_positive": 8.940554847116948,
        "delta": 0.01,
        "compute_epsilon": True,
        "show_governing_point": True,
    },
    "ptr": {
        "loc_negative": 0.6183934157149957,
        "loc_positive": 0.6106134406021159,
        "scale": 0.7186256358849121,
        "scale_negative": 0.7186256358849121,
        "scale_positive": 0.7186256358849121,
        "delta": 0.016666666666666666,
        "compute_epsilon": True,
        "show_governing_point": True,
    },
}


def _theory_embed_cell(key: str) -> dict:
    p = BAKED[key]
    lines = [
        "TheoryROCVisualizer(\n",
        "    distribution='Gaussian',\n",
        f"    scale={p['scale']},\n",
        f"    delta={p['delta']},\n",
        "    selectable_distribution=False,\n",
        f"    loc_negative={p['loc_negative']},\n",
        f"    scale_negative={p['scale_negative']},\n",
        f"    loc_positive={p['loc_positive']},\n",
        f"    scale_positive={p['scale_positive']},\n",
    ]
    if "bound_epsilon" in p:
        lines.append(f"    bound_epsilon={p['bound_epsilon']},\n")
    if p.get("compute_epsilon"):
        lines.append("    compute_epsilon=True,\n")
        lines.append("    show_compute_epsilon_toggle=False,\n")
    lines.append(f"    show_governing_point={p['show_governing_point']},\n")
    lines.append(").embed()\n")
    return {"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None, "source": lines}


def _front_matter() -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            'title: "Private Estimation - cont — Self-study notebook"\n',
            'subtitle: "Applied Data Privacy"\n',
            "format:\n",
            "  html:\n",
            "    page-layout: full\n",
            "    toc: false\n",
            "    toc-depth: 2\n",
            "    code-tools: true\n",
            "    code-fold: true\n",
            "    code-overflow: wrap\n",
            "    include-in-header:\n",
            "      text: |\n",
            "        <style>\n",
            "        .cell-output-display img, .cell-output-display .plotly-graph-div { max-width: 100%; height: auto; }\n",
            "        </style>\n",
            "execute:\n",
            "  enabled: true\n",
            "  warning: false\n",
            "  message: false\n",
            "jupyter: python3\n",
            "---\n",
            "\n",
            "This is the **self-study** companion to the lecture deck: full narrative + all code, meant to be\n",
            "read and run. For the slide version (code hidden), open the [presentation deck](../../lecture-presentations/private-subgroup-comparisons/presentation.html).\n",
        ],
    }


def _setup_cell() -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "outputs": [],
        "execution_count": None,
        "source": [
            "#| output: false\n",
            "#| echo: false\n",
            "try:\n",
            "    get_ipython().run_line_magic('load_ext', 'autoreload')\n",
            "    get_ipython().run_line_magic('autoreload', '2')\n",
            "except Exception:\n",
            "    pass\n",
            "\n",
            "try:\n",
            "    import libdpy\n",
            "except ImportError:\n",
            '    %pip install -q "libdpy[notebook] @ git+https://github.com/applied-dp-course/pub_lib.git"\n',
            "    import libdpy\n",
            "\n",
            "%matplotlib inline\n",
        ],
    }


def _clean_imports(source: str) -> str:
    """Drop duplicate make_* imports introduced during dev iteration."""
    lines = source.splitlines(keepends=True)
    seen_make: set[str] = set()
    out: list[str] = []
    for line in lines:
        m = re.match(r"\s*make_\w+", line.strip().rstrip(","))
        if m:
            name = m.group(0)
            if name in seen_make:
                continue
            seen_make.add(name)
        out.append(line)
    return "".join(out)


def _transform_blog_code(source: str, cell_idx: int) -> str | None:
    """Return None to drop cell; otherwise transformed source."""
    if "TheoryROCVisualizer" in source and ".figure()" in source:
        return None
    source = re.sub(r"\nplt\.show\(\)\n?", "\n", source)
    source = re.sub(
        r"display\(pipeline_artifact\.rows\)\n",
        "pipeline_artifact.rows\n",
        source,
    )
    return source


def _theory_embed_after(cell_idx: int) -> str | None:
    mapping = {16: "global", 22: "typical_oracle", 26: "sparse_oracle", 40: "ptr"}
    return mapping.get(cell_idx)


def build_blog_post() -> None:
    dev = json.loads(DEV_NB.read_text(encoding="utf-8"))
    cells: list[dict] = [_front_matter(), _setup_cell()]

    for idx, cell in enumerate(dev["cells"]):
        if idx == 0:
            continue
        if cell["cell_type"] == "code":
            src = "".join(cell.get("source", []))
            if idx == 1:
                src = _clean_imports(src)
            else:
                transformed = _transform_blog_code(src, idx)
                if transformed is None:
                    embed_key = _theory_embed_after(idx)
                    if embed_key:
                        cells.append(_theory_embed_cell(embed_key))
                    continue
                src = transformed
            cells.append(
                {
                    "cell_type": "code",
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                    "source": [src] if src.endswith("\n") else [src + "\n"],
                }
            )
        else:
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": cell.get("source", []),
                }
            )

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    BLOG.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote blog post: {len(cells)} cells -> {BLOG}")


def build_presentation() -> None:
    qmd = textwrap.dedent(
        """\
        ---
        title: "Private Estimation - cont"
        subtitle: "Denominators, local sensitivity, and private control flow"
        format:
          revealjs:
            theme: white
            slide-number: true
            embed-resources: false
            code-overflow: wrap
            scrollable: true
            css: slides.css
        execute:
          warning: false
          message: false
          echo: false
        jupyter: python3
        ---

        ```{python}
        #| echo: false
        #| output: false
        #| include: false
        try:
            ip = get_ipython()
            if "autoreload" not in ip.extension_manager.loaded:
                ip.run_line_magic("load_ext", "autoreload")
                ip.run_line_magic("autoreload", "2")
        except Exception:
            pass

        try:
            import libdpy
        except ImportError:
            %pip install -q "libdpy[notebook] @ git+https://github.com/applied-dp-course/pub_lib.git"
            import libdpy

        %matplotlib inline
        ```

        ```{python}
        #| echo: false
        #| output: false
        #| include: false
        import numpy as np

        from libdpy.assignment_specific.private_estimation.utils import (
            DEFAULT_DELTA,
            DEFAULT_SEED,
            gaussian_noise_std,
        )
        from libdpy.assignment_specific.private_subgroup_comparisons.lecture_figures import (
            DEFAULT_BETA,
            DEFAULT_SUBGROUP_SAMPLING_DRAW_SIZE,
            PTR_DELTA_FAIL,
            PTR_DELTA_RELEASE,
            PTR_DELTA_TEST,
            PTR_EPS_RELEASE,
            PTR_EPS_TEST,
            SubgroupRepairSpec,
            build_oracle_ls_failure_artifact,
            build_ptr_failure_artifact,
            build_support_comparison_artifact,
            build_above_threshold_support_artifact,
            build_public_menu_artifact,
            build_invalid_selection_witness_artifact,
            build_report_noisy_max_race_artifact,
            build_report_noisy_max_regret_artifact,
            build_above_threshold_selected_level_artifact,
            build_select_then_release_pipeline_artifact,
            build_subgroup_sampling_artifact,
            build_fair_comparison_neighbor_pair,
            evaluate_shared_subgroup_accuracy,
            evaluate_subgroup_accuracy,
            global_sensitivity_release_theory_laws,
            make_subgroup_accuracy_leaderboard_figure,
            make_subgroup_private_methods_population_error_figure,
            make_ptr_failure_probability_figure,
            make_above_threshold_support_figure,
            make_public_menu_support_figure,
            make_invalid_selection_witness_figure,
            make_report_noisy_max_race_figure,
            make_report_noisy_max_regret_figure,
            make_above_threshold_selected_level_figure,
            make_select_then_release_pipeline_figure,
            make_support_comparison_figure,
            make_subgroup_sampling_distribution_figure,
            ptr_conditional_release_theory_laws,
        )
        from libdpy.visualization.roc_plots import TheoryROCVisualizer
        from libdpy.assignment_specific.private_subgroup_comparisons.mechanisms import (
            global_sensitivity_release,
            noisy_count_sum_release,
            oracle_local_sensitivity_output_law,
            ptr_support_release,
            smooth_sensitivity_release,
            subgroup_counts,
        )
        from libdpy.assignment_specific.private_subgroup_comparisons.witnesses import (
            DEFAULT_EPS_TOTAL,
            DEFAULT_FAIR_COMPARISON_MAX_SMALL,
            DEFAULT_FAIR_COMPARISON_MIN_SMALL,
            DEFAULT_SUPPORT_THRESHOLD,
            DEFAULT_TAU,
            DEFAULT_WALKTHROUGH_GROUP_COLUMN,
            PUBLIC_VALUE_UPPER,
            frame_to_arrays,
            prepare_fair_comparison_frame,
            prepare_fulton_subgroup_frame,
        )

        SEED = DEFAULT_SEED
        EPS_TOTAL = DEFAULT_EPS_TOTAL
        DELTA = DEFAULT_DELTA

        frame = prepare_fair_comparison_frame(seed=SEED)
        x, groups = frame_to_arrays(frame, group_column=DEFAULT_WALKTHROUGH_GROUP_COLUMN)
        _, sex_groups = frame_to_arrays(frame, group_column="sex_group")
        walkthrough_counts = subgroup_counts(groups)

        population_df = prepare_fulton_subgroup_frame(n_rows=1_000_000, seed=SEED)
        population_x, population_sex_groups = frame_to_arrays(population_df)
        _, population_latino_groups = frame_to_arrays(population_df, group_column="latino_group")

        LEADERBOARD_N = 1000
        LEADERBOARD_N_DATASETS = 40
        LEADERBOARD_N_RUNS = 5

        (
            fair_x,
            fair_groups,
            fair_x_prime,
            fair_groups_prime,
            _,
            _,
            _,
        ) = build_fair_comparison_neighbor_pair(seed=SEED)


        def subgroup_value_fn(df):
            return df["x"].to_numpy(dtype=float)


        def subgroup_group_fn(df):
            return df[DEFAULT_WALKTHROUGH_GROUP_COLUMN].to_numpy()
        ```

        ## From clipping to subgroup analysis

        ::: {.fragment}
        After a private step controlled the salary scale, subgroup analysis is about **denominators and private control flow**.
        :::

        ::: {.fragment}
        Public contract: clipping interval and reference mean from Lecture 5.
        :::

        ## Roadmap

        ::: {.fragment}
        **Part I:** one subgroup question — audit failures, repair with private control flow.
        :::

        ::: {.fragment}
        **Part II:** public menu of cuts — private validation and selection.
        :::

        ## The statistic

        ::: {.fragment}
        Target: difference of normalized group means on clipped salaries.
        :::

        ::: {.fragment}
        Main demo: **Latino workers vs everyone else**; contrast with stable sex-code groups.
        :::

        ## Sampling variability — stable support

        ::: {.fragment}
        Resampling uncertainty before privacy noise (sex-code groups).
        :::

        ```{python}
        sex_sampling = build_subgroup_sampling_artifact(
            population_x,
            population_sex_groups,
            sample_size=DEFAULT_SUBGROUP_SAMPLING_DRAW_SIZE,
            n_samples=40,
            comparison_label="sex-code groups",
            seed=SEED,
        )
        make_subgroup_sampling_distribution_figure(
            sex_sampling,
            title="Sampling variability — sex-code groups (Fulton)",
        )
        ```

        ## Sampling variability — rare cut

        ::: {.fragment}
        Latino workers vs everyone else (~5% minority): wider histogram before privacy.
        :::

        ```{python}
        latino_sampling = build_subgroup_sampling_artifact(
            population_x,
            population_latino_groups,
            sample_size=DEFAULT_SUBGROUP_SAMPLING_DRAW_SIZE,
            n_samples=40,
            comparison_label="Latino vs everyone else",
            seed=SEED + 1,
        )
        make_subgroup_sampling_distribution_figure(
            latino_sampling,
            title="Sampling variability — Latino walkthrough comparison",
        )
        ```

        ## Global sensitivity is pessimistic

        ::: {.fragment}
        Valid worst-case bound $GS_\\Delta \\le 2B$ — usually not the useful baseline.
        :::

        ## Global sensitivity — theory audit

        ```{python}
        global_theory = global_sensitivity_release_theory_laws(
            fair_x,
            fair_groups,
            fair_x_prime,
            fair_groups_prime,
            epsilon=EPS_TOTAL,
            delta=DELTA,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        TheoryROCVisualizer(
            "Gaussian",
            scale=global_theory.scale,
            delta=global_theory.delta,
            selectable_distribution=False,
            loc_negative=global_theory.loc,
            scale_negative=global_theory.scale,
            loc_positive=global_theory.loc_prime,
            scale_positive=global_theory.scale_prime,
            compute_epsilon=True,
            show_compute_epsilon_toggle=False,
            show_governing_point=True,
        ).figure()
        ```

        ## Global sensitivity leaderboard

        ```{python}
        def global_mechanism(values, group_labels, run_rng):
            return global_sensitivity_release(
                values,
                group_labels,
                EPS_TOTAL,
                run_rng,
                value_bound=PUBLIC_VALUE_UPPER,
                delta=DELTA,
            )


        global_rows = evaluate_subgroup_accuracy(
            population_df,
            global_mechanism,
            n=LEADERBOARD_N,
            n_datasets=LEADERBOARD_N_DATASETS,
            n_runs=LEADERBOARD_N_RUNS,
            seed=SEED,
            group_fn=subgroup_group_fn,
            value_fn=subgroup_value_fn,
            method="global sensitivity",
            privacy_status="valid",
            epsilon_total=EPS_TOTAL,
        )
        make_subgroup_accuracy_leaderboard_figure(
            global_rows,
            title="Global sensitivity release",
        )
        ```

        ## Temptation: oracle local sensitivity

        ::: {.fragment}
        Scale Gaussian noise to a **data-dependent** local-sensitivity bound — not DP when support moves the scale.
        :::

        ## Typical neighbor pair — analytical ROC

        ```{python}
        typical_oracle_loc, _ = oracle_local_sensitivity_output_law(
            fair_x,
            fair_groups,
            EPS_TOTAL,
            DELTA,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        typical_oracle_loc_prime, _ = oracle_local_sensitivity_output_law(
            fair_x_prime,
            fair_groups_prime,
            EPS_TOTAL,
            DELTA,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        typical_oracle_required_std = gaussian_noise_std(
            abs(typical_oracle_loc - typical_oracle_loc_prime),
            EPS_TOTAL,
            DELTA,
        )
        TheoryROCVisualizer(
            "Gaussian",
            scale=typical_oracle_required_std,
            delta=DELTA,
            selectable_distribution=False,
            loc_negative=typical_oracle_loc,
            scale_negative=typical_oracle_required_std,
            loc_positive=typical_oracle_loc_prime,
            scale_positive=typical_oracle_required_std,
            bound_epsilon=EPS_TOTAL,
            show_governing_point=False,
        ).figure()
        ```

        ## Sparse support — privacy failure ROC

        ::: {.fragment}
        Engineered pair: oracle Gaussian std doubles on $D'$ when support drops.
        :::

        ```{python}
        sparse_oracle = build_oracle_ls_failure_artifact(seed=SEED)
        sparse_oracle_loc, sparse_oracle_scale = oracle_local_sensitivity_output_law(
            sparse_oracle.x,
            sparse_oracle.groups,
            EPS_TOTAL,
            DELTA,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        sparse_oracle_loc_prime, sparse_oracle_scale_prime = oracle_local_sensitivity_output_law(
            sparse_oracle.x_prime,
            sparse_oracle.groups_prime,
            EPS_TOTAL,
            DELTA,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        TheoryROCVisualizer(
            "Gaussian",
            scale=sparse_oracle_scale,
            delta=DELTA,
            selectable_distribution=False,
            loc_negative=sparse_oracle_loc,
            scale_negative=sparse_oracle_scale,
            loc_positive=sparse_oracle_loc_prime,
            scale_positive=sparse_oracle_scale_prime,
            compute_epsilon=True,
            show_compute_epsilon_toggle=False,
            show_governing_point=True,
        ).figure()
        ```

        ## Valid repair: noisy counts and sums

        ::: {.fragment}
        Four Gaussian queries + public denominator floor $\\tau$.
        :::

        ```{python}
        def count_sum_mechanism(values, group_labels, run_rng):
            q = EPS_TOTAL / 4
            return noisy_count_sum_release(
                values,
                group_labels,
                q,
                q,
                q,
                q,
                DEFAULT_TAU,
                run_rng,
                value_bound=PUBLIC_VALUE_UPPER,
            )


        count_sum_rows = evaluate_subgroup_accuracy(
            population_df,
            count_sum_mechanism,
            n=LEADERBOARD_N,
            n_datasets=LEADERBOARD_N_DATASETS,
            n_runs=LEADERBOARD_N_RUNS,
            seed=SEED + 1,
            group_fn=subgroup_group_fn,
            value_fn=subgroup_value_fn,
            method="noisy counts and sums",
            privacy_status="valid",
            epsilon_total=EPS_TOTAL,
        )
        make_subgroup_accuracy_leaderboard_figure(
            count_sum_rows,
            title="Noisy counts and sums",
        )
        ```

        ## PTR: test support, then release or abstain

        ::: {.fragment}
        Certify distance from the bad set before releasing with a public sensitivity bound.
        :::

        ```{python}
        ptr_failure = build_ptr_failure_artifact(
            support_values=np.arange(1, 121, dtype=int),
            ptr_threshold=DEFAULT_SUPPORT_THRESHOLD,
            eps_test=PTR_EPS_TEST,
            delta_test=PTR_DELTA_TEST,
            delta_release=PTR_DELTA_RELEASE,
            delta_fail=PTR_DELTA_FAIL,
        )
        make_ptr_failure_probability_figure(
            ptr_failure,
            title="PTR support test failure probability vs true minimum support",
            marker_min_count=min(walkthrough_counts.values()),
            marker_label=f"Latino walkthrough (min n={min(walkthrough_counts.values())})",
        )
        ```

        ## PTR conditional release — theory audit

        ```{python}
        ptr_theory = ptr_conditional_release_theory_laws(
            fair_x,
            fair_groups,
            fair_x_prime,
            fair_groups_prime,
            ptr_threshold=DEFAULT_SUPPORT_THRESHOLD,
            eps_release=PTR_EPS_RELEASE,
            delta_release=PTR_DELTA_RELEASE,
            value_bound=PUBLIC_VALUE_UPPER,
        )
        TheoryROCVisualizer(
            "Gaussian",
            scale=ptr_theory.scale,
            delta=ptr_theory.delta_release,
            selectable_distribution=False,
            loc_negative=ptr_theory.loc,
            scale_negative=ptr_theory.scale,
            loc_positive=ptr_theory.loc_prime,
            scale_positive=ptr_theory.scale_prime,
            compute_epsilon=True,
            show_compute_epsilon_toggle=False,
            show_governing_point=True,
        ).figure()
        ```

        ## PTR accuracy leaderboard

        ```{python}
        def ptr_mechanism(values, group_labels, run_rng):
            return ptr_support_release(
                values,
                group_labels,
                DEFAULT_SUPPORT_THRESHOLD,
                PTR_EPS_TEST,
                PTR_EPS_RELEASE,
                PTR_DELTA_TEST,
                PTR_DELTA_RELEASE,
                PTR_DELTA_FAIL,
                run_rng,
                value_bound=PUBLIC_VALUE_UPPER,
            )


        ptr_rows = evaluate_subgroup_accuracy(
            population_df,
            ptr_mechanism,
            n=LEADERBOARD_N,
            n_datasets=LEADERBOARD_N_DATASETS,
            n_runs=LEADERBOARD_N_RUNS,
            seed=SEED + 2,
            group_fn=subgroup_group_fn,
            value_fn=subgroup_value_fn,
            method="PTR support",
            privacy_status="valid PTR",
            epsilon_total=EPS_TOTAL,
        )
        make_subgroup_accuracy_leaderboard_figure(
            ptr_rows,
            title="PTR support release",
        )
        ```

        ## Smooth sensitivity

        ::: {.fragment}
        NRS Laplace release with admissible $\\beta$ — valid pure-DP repair.
        :::

        ```{python}
        def smooth_mechanism(values, group_labels, run_rng):
            return smooth_sensitivity_release(
                values,
                group_labels,
                EPS_TOTAL,
                DEFAULT_BETA,
                run_rng,
                delta=DELTA,
                value_bound=PUBLIC_VALUE_UPPER,
            )


        smooth_rows = evaluate_subgroup_accuracy(
            population_df,
            smooth_mechanism,
            n=LEADERBOARD_N,
            n_datasets=LEADERBOARD_N_DATASETS,
            n_runs=LEADERBOARD_N_RUNS,
            seed=SEED + 3,
            group_fn=subgroup_group_fn,
            value_fn=subgroup_value_fn,
            method="smooth sensitivity",
            privacy_status="valid smooth sensitivity",
            epsilon_total=EPS_TOTAL,
        )
        make_subgroup_accuracy_leaderboard_figure(
            smooth_rows,
            title="Smooth sensitivity release",
        )
        ```

        ## All valid methods vs population gap

        ```{python}
        private_method_specs = [
            SubgroupRepairSpec(global_mechanism, "global sensitivity", "valid", EPS_TOTAL),
            SubgroupRepairSpec(count_sum_mechanism, "noisy counts and sums", "valid", EPS_TOTAL),
            SubgroupRepairSpec(ptr_mechanism, "PTR support", "valid PTR", EPS_TOTAL),
            SubgroupRepairSpec(smooth_mechanism, "smooth sensitivity", "valid smooth sensitivity", EPS_TOTAL),
        ]
        private_method_rows = evaluate_shared_subgroup_accuracy(
            population_df,
            private_method_specs,
            n=LEADERBOARD_N,
            n_datasets=LEADERBOARD_N_DATASETS,
            n_runs=LEADERBOARD_N_RUNS,
            seed=SEED + 10,
            min_small_support=DEFAULT_FAIR_COMPARISON_MIN_SMALL,
            max_small_support=DEFAULT_FAIR_COMPARISON_MAX_SMALL,
            group_fn=subgroup_group_fn,
            value_fn=subgroup_value_fn,
        )
        make_subgroup_private_methods_population_error_figure(
            private_method_rows,
            title="Released estimate vs population gap — valid private subgroup mechanisms",
        )
        ```

        ## Repairs vs support

        ```{python}
        support_artifact = build_support_comparison_artifact(
            min_support_values=np.array([3, 5, 8, 12, 20, 30, 50, 80, 120]),
            ptr_threshold=DEFAULT_SUPPORT_THRESHOLD,
            n_large=700,
            n_trials=120,
            eps_total=EPS_TOTAL,
            tau=DEFAULT_TAU,
            seed=SEED,
        )
        make_support_comparison_figure(support_artifact)
        ```

        ## Part II — Public menu, private search

        ::: {.fragment}
        Analysts bring a **public menu** of candidate cuts; private data validates or selects through DP.
        :::

        ## Public menu support chart

        ```{python}
        public_menu_artifact = build_public_menu_artifact(seed=SEED)
        make_public_menu_support_figure(public_menu_artifact)
        ```

        ## Invalid non-private selection

        ```{python}
        invalid_selection_artifact = build_invalid_selection_witness_artifact(seed=SEED)
        make_invalid_selection_witness_figure(invalid_selection_artifact)
        ```

        ## Report Noisy Max — support-only utility

        ```{python}
        support_only_race = build_report_noisy_max_race_artifact(
            seed=SEED,
            utility_mode="support_only",
        )
        make_report_noisy_max_race_figure(
            support_only_race,
            title="Report Noisy Max race — support-only utility",
        )
        ```

        ## Report Noisy Max — public priority

        ```{python}
        priority_race = build_report_noisy_max_race_artifact(
            seed=SEED + 1,
            utility_mode="priority_support",
        )
        make_report_noisy_max_race_figure(
            priority_race,
            title="Report Noisy Max race — public priority + support validation",
        )
        ```

        ## Report Noisy Max regret sweep

        ```{python}
        regret_artifact = build_report_noisy_max_regret_artifact(seed=SEED, n_repeats=120)
        make_report_noisy_max_regret_figure(regret_artifact)
        ```

        ## AboveThreshold — ordered menu

        ```{python}
        above_threshold_artifact = build_above_threshold_support_artifact(seed=SEED)
        make_above_threshold_support_figure(
            above_threshold_artifact,
            title="AboveThreshold support ladder: first public coarsening with enough support",
        )
        ```

        ## AboveThreshold selected-level distribution

        ```{python}
        selected_level_artifact = build_above_threshold_selected_level_artifact(
            seed=SEED,
            n_repeats=80,
        )
        make_above_threshold_selected_level_figure(selected_level_artifact)
        ```

        ## Select-then-release pipeline

        ```{python}
        pipeline_artifact = build_select_then_release_pipeline_artifact(seed=SEED, n_runs=60)
        make_select_then_release_pipeline_figure(pipeline_artifact)
        ```

        ## Summary

        ::: {.fragment}
        After clipping, subgroup analysis is about **denominators and private control flow**.
        :::

        ::: {.fragment}
        Private control flow picks the question; Part I mechanisms release $\\Delta$ on the selected grouping.
        :::

        ::: {.fragment}
        Next: private search as a general design pattern and preparing models for private learning.
        :::
        """
    )
    DECK.write_text(qmd, encoding="utf-8")
    print(f"Wrote deck -> {DECK}")


def main() -> None:
    import sys

    blog_only = "--blog-only" in sys.argv
    build_blog_post()
    if not blog_only:
        build_presentation()


if __name__ == "__main__":
    main()
