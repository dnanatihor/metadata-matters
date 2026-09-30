"""Regenerate the README results section from committed run directories."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

START = "<!-- results:start -->"
END = "<!-- results:end -->"


def update_readme(readme: Path, results_root: Path) -> None:
    """Replace only the text between the results markers."""
    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text:
        message = f"README is missing {START} and {END}"
        raise ValueError(message)
    before, rest = text.split(START, maxsplit=1)
    _old, after = rest.split(END, maxsplit=1)
    section = render_results(results_root)
    readme.write_text(f"{before}{START}\n{section}\n{END}{after}", encoding="utf-8")


def _headline(directory: Path) -> str:
    """One value read from the run's metrics file, or a pointer if it is empty."""
    frame = pd.read_csv(directory / "metrics.csv")
    if frame.empty or "estimate" not in frame.columns:
        return "no metrics"
    row = frame.iloc[0]
    estimate = float(row["estimate"])
    return f"`{row.get('label', 'estimate')}` {estimate:.3f}"


def render_results(results_root: Path) -> str:
    """Markdown table built from each RQ's latest ``metrics.csv``."""
    latest = _latest_runs(results_root)
    if not latest:
        return "No committed runs yet."
    lines = [
        "| RQ | Run | Headline |",
        "|---|---|---|",
    ]
    for rq, directory in latest:
        lines.append(f"| {rq} | `{directory.name}` | {_headline(directory)} |")
    lines.append("")
    lines.append("Full tables are in each run's `metrics.csv` and `report.md`.")
    return "\n".join(lines).strip()


def _latest_runs(results_root: Path) -> list[tuple[str, Path]]:
    chosen: dict[str, tuple[str, Path]] = {}
    if not results_root.is_dir():
        return []
    for manifest_path in results_root.glob("*/*/run.json"):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        rq = str(payload.get("rq", manifest_path.parent.parent.name))
        started = str(payload.get("started_at", ""))
        current = chosen.get(rq)
        if current is None or started >= current[0]:
            chosen[rq] = (started, manifest_path.parent)
    return [(rq, chosen[rq][1]) for rq in sorted(chosen)]
