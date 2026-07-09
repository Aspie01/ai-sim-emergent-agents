#!/usr/bin/env python3
"""Generate plots from nested core-replication analysis CSVs."""

from __future__ import annotations

import argparse
import csv
import os
import statistics
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


DEFAULT_ANALYSIS_DIR = Path("experiment_runs/core-replication-v1/analysis")
CONDITIONS = ("baseline", "no_antistag", "no_combat")
CONDITION_LABELS = {
    "baseline": "Baseline",
    "no_antistag": "No anti-stag",
    "no_combat": "No combat",
}
COLORS = {
    "baseline": "#4C78A8",
    "no_antistag": "#F58518",
    "no_combat": "#54A24B",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _by_condition(rows: list[dict[str, str]], field: str) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = {condition: [] for condition in CONDITIONS}
    for row in rows:
        condition = row["condition"]
        if condition in grouped:
            grouped[condition].append(_float(row[field]))
    return grouped


def _boxplot(
    rows: list[dict[str, str]],
    field: str,
    ylabel: str,
    title: str,
    output: Path,
    *,
    log_scale: bool = False,
) -> None:
    grouped = _by_condition(rows, field)
    labels = [CONDITION_LABELS[condition] for condition in CONDITIONS]
    data = [grouped[condition] for condition in CONDITIONS]

    fig, ax = plt.subplots(figsize=(8, 5))
    box = ax.boxplot(data, patch_artist=True, showmeans=True)
    ax.set_xticks(list(range(1, len(labels) + 1)))
    ax.set_xticklabels(labels)
    for patch, condition in zip(box["boxes"], CONDITIONS):
        patch.set_facecolor(COLORS[condition])
        patch.set_alpha(0.45)
    for index, condition in enumerate(CONDITIONS, start=1):
        y_values = grouped[condition]
        x_values = [index + (offset - (len(y_values) - 1) / 2) * 0.035
                    for offset in range(len(y_values))]
        ax.scatter(x_values, y_values, color=COLORS[condition], s=35, zorder=3)
    if log_scale:
        ax.set_yscale("log")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _paired_population_deltas(rows: list[dict[str, str]], output: Path) -> None:
    pairs = [
        ("baseline", "no_antistag", "Baseline → no anti-stag"),
        ("baseline", "no_combat", "Baseline → no combat"),
    ]
    by_pair = defaultdict(list)
    for row in rows:
        pair = (row["reference_condition"], row["comparison_condition"])
        if pair in {(left, right) for left, right, _label in pairs}:
            by_pair[pair].append((int(row["seed"]), _float(row["final_population_delta"])))

    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.35
    seeds = sorted({seed for values in by_pair.values() for seed, _delta in values})
    x_positions = list(range(len(seeds)))
    for pair_index, (left, right, label) in enumerate(pairs):
        values_by_seed = dict(by_pair[(left, right)])
        offsets = [x + (pair_index - 0.5) * width for x in x_positions]
        values = [values_by_seed.get(seed, 0.0) for seed in seeds]
        ax.bar(offsets, values, width=width, label=label)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([str(seed) for seed in seeds])
    ax.set_xlabel("Shared seed")
    ax.set_ylabel("Final population delta")
    ax.set_title("Paired seed final-population deltas")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _event_composition(rows: list[dict[str, str]], output: Path) -> list[dict]:
    by_condition = defaultdict(lambda: defaultdict(int))
    for row in rows:
        by_condition[row["condition"]][row["event_type"]] += int(row["count"])

    event_totals = defaultdict(int)
    for counts in by_condition.values():
        for event_type, count in counts.items():
            event_totals[event_type] += count
    top_events = [
        event_type for event_type, _count in
        sorted(event_totals.items(), key=lambda item: item[1], reverse=True)[:9]
    ]

    table_rows = []
    bottoms = [0] * len(CONDITIONS)
    fig, ax = plt.subplots(figsize=(10, 6))
    for event_type in top_events:
        values = [by_condition[condition].get(event_type, 0) for condition in CONDITIONS]
        ax.bar(
            [CONDITION_LABELS[condition] for condition in CONDITIONS],
            values,
            bottom=bottoms,
            label=event_type,
        )
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    ax.set_yscale("log")
    ax.set_ylabel("Structured event count, log scale")
    ax.set_title("Event-type composition by condition")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)

    for condition in CONDITIONS:
        total = sum(by_condition[condition].values())
        for event_type in sorted(by_condition[condition]):
            count = by_condition[condition][event_type]
            table_rows.append({
                "condition": condition,
                "event_type": event_type,
                "count": count,
                "fraction": round(count / total, 8) if total else 0.0,
            })
    return table_rows


def _summary_table(rows: list[dict[str, str]]) -> list[dict]:
    fields = [
        "final_population",
        "final_faction_count",
        "elapsed_seconds",
        "output_gib",
        "event_count",
    ]
    table = []
    for condition in CONDITIONS:
        group = [row for row in rows if row["condition"] == condition]
        out = {"condition": condition, "n_runs": len(group)}
        for field in fields:
            values = [_float(row[field]) for row in group]
            out[f"{field}_mean"] = round(statistics.fmean(values), 6)
            out[f"{field}_median"] = round(statistics.median(values), 6)
            out[f"{field}_min"] = round(min(values), 6)
            out[f"{field}_max"] = round(max(values), 6)
        table.append(out)
    return table


def write_report(figures_dir: Path, summary_rows: list[dict], event_rows: list[dict]) -> None:
    report = figures_dir.parent / "CORE_REPLICATION_PLOTS_REPORT.md"
    lines = [
        "# Core Replication Plots Report",
        "",
        f"Figures generated under `{figures_dir}`.",
        "",
        "## Figures",
        "",
        "- `final_population_by_condition.png`",
        "- `final_factions_by_condition.png`",
        "- `elapsed_time_by_condition.png`",
        "- `output_size_by_condition.png`",
        "- `event_count_by_condition.png`",
        "- `paired_seed_final_population_deltas.png`",
        "- `event_type_composition_by_condition.png`",
        "",
        "## Condition summary table",
        "",
        "| Condition | n | Mean final pop | Mean final factions | Mean elapsed s | Mean output GiB | Mean events |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['condition']} | {row['n_runs']} | "
            f"{row['final_population_mean']:.2f} | "
            f"{row['final_faction_count_mean']:.2f} | "
            f"{row['elapsed_seconds_mean']:.2f} | "
            f"{row['output_gib_mean']:.3f} | "
            f"{row['event_count_mean']:.0f} |"
        )
    lines.extend([
        "",
        "## Event composition table",
        "",
        "See `event_type_composition_table.csv` for counts and within-condition fractions.",
        "",
        "The no-combat condition is dominated by `raid` events, which is why the "
        "composition plot uses a log-scaled y-axis.",
        "",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    args = parser.parse_args()

    analysis_dir = args.analysis_dir
    figures_dir = analysis_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    run_rows = _read_csv(analysis_dir / "run_level_summary.csv")
    pair_rows = _read_csv(analysis_dir / "paired_seed_comparisons.csv")
    event_rows = _read_csv(analysis_dir / "event_type_counts.csv")

    _boxplot(
        run_rows,
        "final_population",
        "Final population",
        "Final population by condition",
        figures_dir / "final_population_by_condition.png",
    )
    _boxplot(
        run_rows,
        "final_faction_count",
        "Final active factions",
        "Final factions by condition",
        figures_dir / "final_factions_by_condition.png",
    )
    _boxplot(
        run_rows,
        "elapsed_seconds",
        "Elapsed seconds",
        "Elapsed time by condition",
        figures_dir / "elapsed_time_by_condition.png",
        log_scale=True,
    )
    _boxplot(
        run_rows,
        "output_gib",
        "Output size, GiB",
        "Output size by condition",
        figures_dir / "output_size_by_condition.png",
        log_scale=True,
    )
    _boxplot(
        run_rows,
        "event_count",
        "Structured event count",
        "Event count by condition",
        figures_dir / "event_count_by_condition.png",
        log_scale=True,
    )
    _paired_population_deltas(
        pair_rows,
        figures_dir / "paired_seed_final_population_deltas.png",
    )
    composition_rows = _event_composition(
        event_rows,
        figures_dir / "event_type_composition_by_condition.png",
    )
    summary_rows = _summary_table(run_rows)
    _write_csv(
        figures_dir / "condition_plot_summary_table.csv",
        summary_rows,
        list(summary_rows[0]),
    )
    _write_csv(
        figures_dir / "event_type_composition_table.csv",
        composition_rows,
        ["condition", "event_type", "count", "fraction"],
    )
    write_report(figures_dir, summary_rows, composition_rows)
    print(f"Wrote figures and plot report under {figures_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
