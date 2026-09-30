"""Bar charts for a run directory."""

from __future__ import annotations

from pathlib import Path


def bar_plot(labels: list[str], values: list[float], path: Path, *, ylabel: str) -> None:
    """Write one PNG. Headless; no window is opened."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 4), constrained_layout=True)
    axis.bar(labels, values)
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", labelrotation=60, labelsize=7)
    figure.savefig(path)
    plt.close(figure)
