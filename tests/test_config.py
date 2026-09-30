"""Phase 0: config models load the committed YAML files."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from mm.config import (
    ModelKind,
    PricesConfig,
    RunConfig,
    SampleConfig,
    configs_dir,
    load_models_config,
    load_prices_config,
    load_run_config,
    load_yaml_model,
)


def test_run_configs_load_with_default_sample() -> None:
    root = configs_dir()
    for name in ("rq1", "rq2", "rq3", "rq4"):
        loaded = load_run_config(root / f"{name}.yaml")
        assert loaded.rq == name
        assert loaded.sample.n == 500
        assert loaded.sample.seed == 0
        assert loaded.budget.max_usd == 0


def test_rq3_names_two_local_embedding_models() -> None:
    root = configs_dir()
    models = load_models_config(root / "models.yaml")
    embeddings = [model for model in models.models if model.kind is ModelKind.EMBEDDING]
    local = [model for model in embeddings if model.provider == "sentence-transformers"]
    assert len(local) >= 2
    prices = load_prices_config(root / "prices.yaml")
    priced = {price.model_id for price in prices.prices}
    assert {model.id for model in local} <= priced
    for price in prices.prices:
        assert price.usd_per_million_input_tokens >= 0
        assert price.usd_per_million_output_tokens >= 0
    run = load_run_config(root / "rq3.yaml")
    known = {model.id for model in models.models}
    assert set(run.models) == {model.id for model in local}
    assert set(run.models) <= known


def test_sample_all_and_negative_budget(tmp_path: Path) -> None:
    path = tmp_path / "sample.yaml"
    path.write_text("n: all\nseed: 1\n", encoding="utf-8")
    loaded = load_yaml_model(path, SampleConfig)
    assert loaded.n == "all"
    bad_n = tmp_path / "bad_n.yaml"
    bad_n.write_text("n: 0\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_yaml_model(bad_n, SampleConfig)
    bad_budget = tmp_path / "bad_budget.yaml"
    bad_budget.write_text(
        "rq: rq1\nbudget:\n  max_usd: -1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_yaml_model(bad_budget, RunConfig)
    bad_price = tmp_path / "bad_price.yaml"
    bad_price.write_text(
        "prices:\n"
        "  - model_id: x\n"
        "    usd_per_million_input_tokens: -0.1\n"
        "    usd_per_million_output_tokens: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_yaml_model(bad_price, PricesConfig)
