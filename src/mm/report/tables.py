"""Metrics tables and the markdown report beside them."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mm.report.plots import bar_plot

M3_CAVEAT = (
    "M3 adds the example's own BIRD evidence, labelled as a business glossary hint. "
    "That hint is question-specific, not a property of the table."
)


def write_metrics_report(
    output_dir: Path,
    *,
    title: str,
    rows: list[dict[str, object]],
    label_column: str,
    value_column: str,
    caveats: list[str],
) -> None:
    """Write ``metrics.csv``, ``plots/metrics.png``, and ``report.md``."""
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "metrics.csv", index=False)
    plot_path = output_dir / "plots" / "metrics.png"
    if frame.empty:
        bar_plot(["none"], [0.0], plot_path, ylabel=value_column)
    else:
        bar_plot(
            [str(value) for value in frame[label_column].tolist()],
            [float(value) for value in frame[value_column].tolist()],
            plot_path,
            ylabel=value_column,
        )
    lines = [
        f"# {title}",
        "",
        "## Method",
        "",
        "Fixture run with stub models. Numbers below are read from metrics.csv.",
        "",
        "## Results",
        "",
        markdown_table(frame) if not frame.empty else "_No rows._",
        "",
        "## Plots",
        "",
        "![metrics](plots/metrics.png)",
        "",
        "## Caveats",
        "",
    ]
    if not caveats:
        caveats = ["Results describe this run's models, prompts, and date only."]
    lines.extend(f"- {caveat}" for caveat in caveats)
    lines.append("")
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row[column]) for column in columns) + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, separator, *body])


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows
