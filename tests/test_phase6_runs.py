"""Committed fixture runs and the generated README results section."""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path("results")
README = Path("README.md")


def test_every_committed_run_has_a_manifest_and_outputs() -> None:
    runs = sorted(path.parent for path in RESULTS.glob("*/*/run.json"))
    assert {run.parent.name for run in runs} == {"rq1", "rq2", "rq3", "rq4"}
    for run in runs:
        manifest = json.loads((run / "run.json").read_text(encoding="utf-8"))
        assert manifest["run_id"] == run.name
        assert manifest["rq"] == run.parent.name
        assert (run / "metrics.csv").is_file()
        assert (run / "report.md").is_file()
        assert list((run / "plots").glob("*.png"))


def test_readme_results_section_names_the_committed_runs() -> None:
    text = README.read_text(encoding="utf-8")
    start = text.index("<!-- results:start -->")
    end = text.index("<!-- results:end -->")
    section = text[start:end]
    assert section.strip() != "<!-- results:start -->"
    for run in RESULTS.glob("*/*"):
        if (run / "run.json").is_file():
            assert run.name in section
