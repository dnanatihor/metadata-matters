"""Phase 5: fixture runs write reports and plots; mm readme edits only its section."""

from __future__ import annotations

from pathlib import Path

from mm.config import (
    SampleConfig,
    configs_dir,
    load_models_config,
    load_prices_config,
    load_run_config,
)
from mm.data.fixture import load_fixture
from mm.report.readme import update_readme
from mm.suite import rebuild_report, run_fixture


def test_fixture_runs_of_all_four_rqs_produce_reports_and_plots(tmp_path: Path) -> None:
    dataset = load_fixture()
    root = configs_dir()
    prices = load_prices_config(root / "prices.yaml")
    models = load_models_config(root / "models.yaml")
    for rq in ("rq1", "rq2", "rq3", "rq4"):
        config = load_run_config(root / f"{rq}.yaml").model_copy(
            update={"sample": SampleConfig(n=2, seed=0)}
        )
        output = run_fixture(dataset, config, prices, models, tmp_path / rq, tmp_path / "cache.db")
        assert (output / "run.json").is_file()
        assert (output / "metrics.csv").is_file()
        assert (output / "report.md").is_file()
        assert list((output / "plots").glob("*.png"))
        rebuild_report(output)
        assert (output / "report.md").is_file()
    report = (tmp_path / "rq1" / "report.md").read_text(encoding="utf-8")
    assert "question-specific" in report


def test_readme_updates_only_the_marked_section(tmp_path: Path) -> None:
    dataset = load_fixture()
    root = configs_dir()
    config = load_run_config(root / "rq1.yaml").model_copy(
        update={"sample": SampleConfig(n=2, seed=0)}
    )
    run_dir = tmp_path / "results" / "rq1" / "demo"
    run_fixture(
        dataset,
        config,
        load_prices_config(root / "prices.yaml"),
        load_models_config(root / "models.yaml"),
        run_dir,
        tmp_path / "cache.db",
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "HEAD\n<!-- results:start -->\nOLD\n<!-- results:end -->\nTAIL\n", encoding="utf-8"
    )
    update_readme(readme, tmp_path / "results")
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("HEAD\n")
    assert text.endswith("TAIL\n")
    assert "OLD" not in text
    assert "<!-- results:start -->" in text
    assert "<!-- results:end -->" in text
