"""Phase 2: cache resume, budget guard, backoff, and run.json."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from mm.config import (
    BudgetConfig,
    PricesConfig,
    RunConfig,
    SampleConfig,
    TokenPrice,
    configs_dir,
    load_prices_config,
)
from mm.context.levels import MetadataLevel
from mm.data.fixture import load_fixture
from mm.llm.budget import BudgetExceededError
from mm.llm.cache import ResponseCache
from mm.llm.runner import RateLimitError, complete_with_backoff, run_rq1
from mm.llm.stub import Completion, GoldSqlStub


def test_request_hash_is_sha256_of_model_version_and_prompt(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "cache.db")
    digest = hashlib.sha256(b"stub-gold|text_to_sql.v1|hello").hexdigest()
    assert cache.request_hash("stub-gold", "text_to_sql.v1", "hello") == digest


def test_rerun_of_a_completed_fixture_run_makes_zero_model_calls(tmp_path: Path) -> None:
    dataset = load_fixture()
    config = RunConfig(rq="rq1", sample=SampleConfig(n=2, seed=0), budget=BudgetConfig(max_usd=0))
    prices = load_prices_config(configs_dir() / "prices.yaml")
    stub = GoldSqlStub()
    cache = tmp_path / "cache.db"
    kwargs = {
        "dataset": dataset,
        "config": config,
        "prices": prices,
        "clients": [stub],
        "cache_path": cache,
        "levels": [MetadataLevel.M0, MetadataLevel.M1],
        "timeout_s": 5.0,
        "concurrency": {"stub": 1},
    }
    first = run_rq1(output_dir=tmp_path / "run-a", **kwargs)
    assert stub.calls == 4
    manifest = json.loads((first / "run.json").read_text(encoding="utf-8"))
    assert manifest["sample_ids_file"] == "sample.json"
    assert manifest["prompt_version"] == "text_to_sql.v1"
    assert manifest["model_ids"] == ["stub-gold"]
    assert manifest["git_commit"]
    assert "metadata-matters" in manifest["package_versions"]
    assert (first / "sample.json").is_file()
    stub.calls = 0
    run_rq1(output_dir=tmp_path / "run-b", **kwargs)
    assert stub.calls == 0


def test_budget_guard_refuses_when_the_estimate_exceeds_the_cap(tmp_path: Path) -> None:
    dataset = load_fixture()
    config = RunConfig(
        rq="rq1", sample=SampleConfig(n=2, seed=0), budget=BudgetConfig(max_usd=0.0001)
    )
    prices = PricesConfig(
        prices=[
            TokenPrice(
                model_id="stub-gold",
                usd_per_million_input_tokens=0,
                usd_per_million_output_tokens=1_000_000,
            )
        ]
    )
    stub = GoldSqlStub()
    with pytest.raises(BudgetExceededError):
        run_rq1(
            dataset=dataset,
            config=config,
            prices=prices,
            clients=[stub],
            output_dir=tmp_path / "refused",
            cache_path=tmp_path / "cache.db",
            levels=[MetadataLevel.M0],
            timeout_s=5.0,
        )
    assert stub.calls == 0
    assert not (tmp_path / "refused" / "run.json").exists()


def test_actual_spend_stops_the_run(tmp_path: Path) -> None:
    dataset = load_fixture()

    class Expensive(GoldSqlStub):
        def complete(self, full_prompt: str, *, example: object) -> Completion:
            self.calls += 1
            return Completion(text="```sql\nSELECT 1\n```", input_tokens=1, output_tokens=1_000_000)

    stub = Expensive()
    prices = PricesConfig(
        prices=[
            TokenPrice(
                model_id="stub-gold",
                usd_per_million_input_tokens=0,
                usd_per_million_output_tokens=1,
            )
        ]
    )
    config = RunConfig(rq="rq1", sample=SampleConfig(n=4, seed=0), budget=BudgetConfig(max_usd=0.5))
    output = run_rq1(
        dataset=dataset,
        config=config,
        prices=prices,
        clients=[stub],
        output_dir=tmp_path / "stopped",
        cache_path=tmp_path / "cache.db",
        levels=[MetadataLevel.M0],
        timeout_s=5.0,
        concurrency={"stub": 1},
    )
    assert stub.calls == 1
    manifest = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert manifest["cost_usd"] == pytest.approx(1.0)


def test_provider_concurrency_cap(tmp_path: Path) -> None:
    dataset = load_fixture()
    state = {"current": 0, "peak": 0}
    lock = threading.Lock()

    class Limited(GoldSqlStub):
        def complete(self, full_prompt: str, *, example: object) -> Completion:
            with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            time.sleep(0.05)
            with lock:
                state["current"] -= 1
            return Completion(text="```sql\nSELECT 1\n```", input_tokens=1, output_tokens=1)

    config = RunConfig(rq="rq1", sample=SampleConfig(n=4, seed=0), budget=BudgetConfig(max_usd=1))
    run_rq1(
        dataset=dataset,
        config=config,
        prices=load_prices_config(configs_dir() / "prices.yaml"),
        clients=[Limited()],
        output_dir=tmp_path / "limited",
        cache_path=tmp_path / "cache.db",
        levels=[MetadataLevel.M0],
        timeout_s=5.0,
        concurrency={"stub": 2},
    )
    assert state["peak"] == 2


def test_rate_limit_backoff_doubles_the_delay() -> None:
    attempts = {"n": 0}

    def call() -> Completion:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RateLimitError("slow down")
        return Completion(text="ok", input_tokens=1, output_tokens=1)

    slept: list[float] = []
    result = complete_with_backoff(call, sleeper=slept.append, base_delay_s=0.25)
    assert result.text == "ok"
    assert slept == [0.25, 0.5]
