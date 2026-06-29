#!/usr/bin/env python3
"""
Statistical significance analysis for variant graph node counts.
Runs Friedman test (global significance) and post-hoc Wilcoxon signed-rank tests
with Holm-Bonferroni correction.
"""

import argparse
import os
import sys
from collections import defaultdict

# Define the expected strategies
STRATEGIES = [
    "Enriched (lemma+pos)",
    "Enriched (lemma)",
    "Enriched (text)",
]


def check_dependencies():
    """Verify that the required libraries are installed."""
    missing = []
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        missing.append("numpy")

    try:
        import scipy.stats as stats  # noqa: F401
    except ImportError:
        missing.append("scipy")

    try:
        import statsmodels.stats.multitest as multitest  # noqa: F401
    except ImportError:
        missing.append("statsmodels")

    if missing:
        print("Error: Missing required packages for statistical analysis.")
        print(
            f"Please install them via: uv add {' '.join(missing)}  (or pip install {' '.join(missing)})"
        )
        sys.exit(1)


def parse_csv(csv_path):
    """Reads the CSV and aligns the node counts by reference.

    Only returns references that have observations for all 3 enriched strategies.
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'")
        sys.exit(1)

    import csv

    raw_data = defaultdict(dict)

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ref = row["reference"]
                config = row["config_name"]
                nodes = int(row["nodes"])
                raw_data[ref][config] = nodes
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping malformed row: {row} ({e})")

    # Filter for references that have all 4 strategies
    aligned_refs = []
    data_by_strategy = {strat: [] for strat in STRATEGIES}

    for ref, configs in raw_data.items():
        if all(strat in configs for strat in STRATEGIES):
            aligned_refs.append(ref)
            for strat in STRATEGIES:
                data_by_strategy[strat].append(configs[strat])

    print(f"Loaded {len(aligned_refs)} valid, fully-paired references from CSV.")
    return data_by_strategy, aligned_refs


def main():
    parser = argparse.ArgumentParser(
        description="Run statistical significance tests on variant graph node counts."
    )
    parser.add_argument(
        "--csv",
        default="docs/variant_graph_reference_metrics.csv",
        help="Path to the reference-level CSV metrics file",
    )
    args = parser.parse_args()

    check_dependencies()

    import numpy as np
    import scipy.stats as stats
    import statsmodels.stats.multitest as multitest

    data_by_strategy, refs = parse_csv(args.csv)

    if not refs:
        print("Error: No aligned reference data found. Cannot run tests.")
        sys.exit(1)

    if len(refs) < 5:
        print(
            "Warning: Sample size (N) is very small. Statistical tests may lack power."
        )

    # 1. Global test: Friedman Test
    groups = [data_by_strategy[strat] for strat in STRATEGIES]
    stat, p_global = stats.friedmanchisquare(*groups)

    print("=" * 80)
    print("GLOBAL STATISTICAL SIGNIFICANCE (FRIEDMAN TEST)")
    print("=" * 80)
    print(f"Friedman chi-square statistic: {stat:.4f}")
    print(f"P-value:                      {p_global:.4e}")

    alpha = 0.05
    is_significant = p_global < alpha
    print(f"Significant (alpha={alpha}):     {'YES' if is_significant else 'NO'}")
    print("=" * 80)

    if not is_significant:
        print(
            "\nNo statistically significant difference was found across the strategies overall."
        )
        return

    # 2. Pairwise Post-Hoc Wilcoxon Signed-Rank Tests
    print("\n" + "=" * 80)
    print(
        "PAIRWISE POST-HOC COMPARISONS (WILCOXON SIGNED-RANK TEST WITH HOLM CORRECTION)"
    )
    print("=" * 80)

    p_values = []
    pairs = []

    # Get all combinations
    num_strats = len(STRATEGIES)
    for i in range(num_strats):
        for j in range(i + 1, num_strats):
            strat_a = STRATEGIES[i]
            strat_b = STRATEGIES[j]
            vals_a = np.array(data_by_strategy[strat_a])
            vals_b = np.array(data_by_strategy[strat_b])

            # Wilcoxon signed-rank test
            if np.all(vals_a == vals_b):
                p_val = 1.0
            else:
                # alternative="two-sided" is default
                _, p_val = stats.wilcoxon(vals_a, vals_b)

            mean_diff = np.mean(vals_a - vals_b)
            p_values.append(p_val)
            pairs.append((strat_a, strat_b, mean_diff))

    # Apply Holm-Bonferroni correction
    reject, p_corrected, _, _ = multitest.multipletests(
        p_values, alpha=alpha, method="holm"
    )

    # Print results in a markdown table
    headers = [
        "Comparison (A vs B)",
        "Mean Diff (A - B)",
        "Raw p-value",
        "Holm-adj p-value",
        "Significant?",
    ]
    print(
        f"| {headers[0]:<42} | {headers[1]:<17} | {headers[2]:<12} | {headers[3]:<16} | {headers[4]:<12} |"
    )
    print(f"|{'-' * 44}|{'-' * 19}|{'-' * 14}|{'-' * 18}|{'-' * 14}|")

    for idx, (strat_a, strat_b, mean_diff) in enumerate(pairs):
        comp_label = f"{strat_a} vs {strat_b}"
        sig_str = "YES" if reject[idx] else "NO"
        print(
            f"| {comp_label:<42} "
            f"| {mean_diff:<+17.2f} "
            f"| {p_values[idx]:<12.4e} "
            f"| {p_corrected[idx]:<16.4e} "
            f"| {sig_str:<12} |"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
