"""Resumable RQ1 runner: cache, budget, concurrency, backoff, and ``run.json``."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from mm.config import PricesConfig, RunConfig
from mm.context.levels import MetadataLevel, build_schema
from mm.data.bird import Dataset, Example
from mm.data.sample import stratified_sample
from mm.evaluate.execution import judge_execution
from mm.llm.budget import (
    call_cost,
    estimate_call_cost,
    price_for,
    require_within_budget,
)
from mm.llm.cache import CachedCompletion, ResponseCache
from mm.llm.extract_sql import extract_sql
from mm.llm.stub import Completion, GoldSqlStub
from mm.paths import repo_root
from mm.prompt import PROMPT_VERSION, render_text_to_sql

_PACKAGES = ("metadata-matters", "numpy", "pydantic", "scipy")


class RateLimitError(Exception):
    """The provider asked the runner to back off."""


class ChatClient(Protocol):
    model_id: str
    provider: str

    def complete(self, full_prompt: str, *, example: Example) -> Completion:
        """Return the model text and token counts for one prompt."""


Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class PromptJob:
    example: Example
    level: MetadataLevel
    model_id: str
    provider: str
    full_prompt: str
    estimated_usd: float


@dataclass(frozen=True)
class Prediction:
    question_id: int
    db_id: str
    difficulty: str
    level: str
    model_id: str
    sql: str | None
    correct: bool
    cause: str | None
    cached: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float


def complete_with_backoff(
    call: Callable[[], Completion],
    *,
    sleeper: Sleeper = time.sleep,
    max_attempts: int = 5,
    base_delay_s: float = 0.5,
) -> Completion:
    """Retry rate-limit errors with exponential backoff. Other errors propagate."""
    delay = base_delay_s
    for attempt in range(max_attempts):
        try:
            return call()
        except RateLimitError:
            if attempt == max_attempts - 1:
                raise
            sleeper(delay)
            delay *= 2
    message = "unreachable"
    raise RuntimeError(message)


def run_rq1(
    *,
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    clients: Sequence[ChatClient],
    output_dir: Path,
    cache_path: Path,
    levels: Sequence[MetadataLevel] | None = None,
    timeout_s: float = 30.0,
    concurrency: dict[str, int] | None = None,
    sleeper: Sleeper = time.sleep,
) -> Path:
    """Run RQ1. Writes ``run.json`` after a started run. Refuses an over-budget estimate."""
    chosen_levels = (
        list(levels)
        if levels is not None
        else [MetadataLevel(level) for level in ("M0", "M1", "M2", "M3")]
    )
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    by_id = {client.model_id: client for client in clients}
    jobs = _build_jobs(dataset, sample, chosen_levels, clients, prices)
    estimated = sum(job.estimated_usd for job in jobs)
    require_within_budget(estimated, config.budget.max_usd)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "sample.json", [example.question_id for example in sample])
    started = _now()
    cache = ResponseCache(cache_path)
    predictions, spent, usage = _execute_jobs(
        dataset,
        jobs,
        by_id,
        prices,
        cache,
        config.budget.max_usd,
        concurrency or {},
        sleeper,
        timeout_s,
    )
    ended = _now()
    _write_predictions(output_dir / "predictions.jsonl", predictions)
    manifest = {
        "run_id": output_dir.name,
        "git_commit": _git_commit(),
        "package_versions": _package_versions(),
        "model_ids": sorted({job.model_id for job in jobs}),
        "prompt_version": PROMPT_VERSION,
        "template_versions": [],
        "dataset_checksum": dataset_checksum(dataset),
        "sample_ids_file": "sample.json",
        "seed": config.sample.seed,
        "started_at": started,
        "ended_at": ended,
        "token_usage": usage,
        "cost_usd": spent,
        "rq": config.rq,
        "estimated_usd": estimated,
        "item_count": len(jobs),
    }
    _write_json(output_dir / "run.json", manifest)
    return output_dir


def dataset_checksum(dataset: Dataset) -> str:
    """SHA-256 over ``dev.json`` and each SQLite file."""
    import hashlib

    digest = hashlib.sha256()
    digest.update((dataset.root / "dev.json").read_bytes())
    for database in sorted(dataset.databases, key=lambda item: item.db_id):
        digest.update(database.db_id.encode())
        digest.update(database.sqlite_path.read_bytes())
    return digest.hexdigest()


def dry_run_summary(
    *,
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    clients: Sequence[ChatClient],
    levels: Sequence[MetadataLevel] | None = None,
) -> tuple[int, float]:
    """Item count and cost estimate. Does not call a model or write a run."""
    chosen = (
        list(levels)
        if levels is not None
        else [MetadataLevel(level) for level in ("M0", "M1", "M2", "M3")]
    )
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    jobs = _build_jobs(dataset, sample, chosen, clients, prices)
    return len(jobs), sum(job.estimated_usd for job in jobs)


def _build_jobs(
    dataset: Dataset,
    sample: tuple[Example, ...],
    levels: list[MetadataLevel],
    clients: Sequence[ChatClient],
    prices: PricesConfig,
) -> list[PromptJob]:
    jobs: list[PromptJob] = []
    descriptions = {
        database.db_id: dataset.column_descriptions(database.db_id)
        for database in dataset.databases
    }
    for example in sample:
        database = dataset.database(example.db_id)
        for level in levels:
            schema = build_schema(
                database,
                level,
                evidence=example.evidence,
                descriptions=descriptions[example.db_id],
            )
            rendered = render_text_to_sql(schema, example.question)
            for client in clients:
                price = price_for(prices, client.model_id)
                jobs.append(
                    PromptJob(
                        example=example,
                        level=level,
                        model_id=client.model_id,
                        provider=client.provider,
                        full_prompt=rendered.full_prompt,
                        estimated_usd=estimate_call_cost(rendered.full_prompt, price),
                    )
                )
    return jobs


def _execute_jobs(
    dataset: Dataset,
    jobs: list[PromptJob],
    clients: dict[str, ChatClient],
    prices: PricesConfig,
    cache: ResponseCache,
    max_usd: float,
    concurrency: dict[str, int],
    sleeper: Sleeper,
    timeout_s: float,
) -> tuple[list[Prediction], float, dict[str, int]]:
    spent = 0.0
    spent_lock = threading.Lock()
    stop = threading.Event()
    predictions: list[Prediction] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    providers = {job.provider for job in jobs}
    semaphores = {
        provider: threading.Semaphore(concurrency.get(provider, 4)) for provider in providers
    }
    width = max(1, sum(concurrency.get(provider, 4) for provider in providers)) if providers else 1

    def worker(job: PromptJob) -> Prediction | None:
        nonlocal spent
        if stop.is_set():
            return None
        with semaphores[job.provider]:
            if stop.is_set():
                return None
            request_hash = cache.request_hash(job.model_id, PROMPT_VERSION, job.full_prompt)
            hit = cache.get(request_hash)
            from_cache = hit is not None
            if hit is None:
                client = clients[job.model_id]

                def invoke() -> Completion:
                    return client.complete(job.full_prompt, example=job.example)

                fresh = complete_with_backoff(invoke, sleeper=sleeper)
                hit = CachedCompletion(fresh.text, fresh.input_tokens, fresh.output_tokens)
                cache.put(request_hash, hit)
            price = price_for(prices, job.model_id)
            cost = 0.0 if from_cache else call_cost(hit.input_tokens, hit.output_tokens, price)
            with spent_lock:
                spent += cost
                if not from_cache:
                    usage["input_tokens"] += hit.input_tokens
                    usage["output_tokens"] += hit.output_tokens
                if cost > 0 and spent >= max_usd:
                    stop.set()
            predicted = extract_sql(hit.text)
            database = dataset.database(job.example.db_id)
            judgement = judge_execution(database, job.example.sql, predicted, timeout_s=timeout_s)
            return Prediction(
                question_id=job.example.question_id,
                db_id=job.example.db_id,
                difficulty=job.example.difficulty.value,
                level=job.level.value,
                model_id=job.model_id,
                sql=predicted,
                correct=judgement.correct,
                cause=judgement.cause,
                cached=from_cache,
                input_tokens=hit.input_tokens,
                output_tokens=hit.output_tokens,
                cost_usd=cost,
            )

    if jobs:
        with ThreadPoolExecutor(max_workers=min(len(jobs), width)) as pool:
            pending: set[Future[Prediction | None]] = set()
            next_index = 0
            while next_index < len(jobs) or pending:
                while next_index < len(jobs) and len(pending) < width and not stop.is_set():
                    pending.add(pool.submit(worker, jobs[next_index]))
                    next_index += 1
                if not pending:
                    break
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    result = future.result()
                    if result is not None:
                        predictions.append(result)
    predictions.sort(key=lambda item: (item.question_id, item.level, item.model_id))
    return predictions, spent, usage


def fixture_clients() -> list[GoldSqlStub]:
    return [GoldSqlStub()]


def _write_predictions(path: Path, predictions: list[Prediction]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(prediction.__dict__, sort_keys=True) + "\n")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git_commit() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return output.strip()


def _package_versions() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in _PACKAGES:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = "unknown"
    return found
