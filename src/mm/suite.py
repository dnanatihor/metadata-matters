"""Fixture runs for RQ1-RQ4 and the report each of them writes."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import sqlglot

from mm.config import ModelKind, ModelsConfig, PricesConfig, RunConfig, TokenPrice
from mm.context.levels import MetadataLevel, build_retrieved_m2, build_schema
from mm.data.bird import Dataset, Example
from mm.data.sample import stratified_sample
from mm.decoys import (
    FIXTURE_DECOY_SEED,
    DecoyCondition,
    build_decoy_database,
    condition_schema,
    uses_decoy,
)
from mm.evaluate.execution import judge_execution
from mm.evaluate.relevance import extract_relevance
from mm.evaluate.retrieval_metrics import (
    full_coverage_at_k,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mm.evaluate.stats import bootstrap_mean_ci
from mm.llm.budget import call_cost, estimate_call_cost, price_for, require_within_budget
from mm.llm.cache import CachedCompletion, ResponseCache
from mm.llm.extract_sql import extract_sql
from mm.llm.langchain_chat import LangChainChat
from mm.llm.runner import ChatClient, dataset_checksum, dry_run_summary, run_rq1, write_manifest
from mm.llm.stub import GoldSqlStub
from mm.prompt import PROMPT_VERSION, render_text_to_sql
from mm.report.tables import M3_CAVEAT, read_jsonl, write_metrics_report
from mm.retrieval.corpus import TEMPLATES, Document, build_corpus, corpus_hash
from mm.retrieval.embed import Embedder, HashEmbedder, cached_embed
from mm.retrieval.index import rank_documents
from mm.retrieval.local_embed import SentenceTransformerEmbedder

QUERY_MODES = ("question", "question_evidence")
SETTINGS = ("in_database", "global")
TOP_K = (10, 20)


def fixture_summary(
    dataset: Dataset, config: RunConfig, prices: PricesConfig, models: ModelsConfig
) -> tuple[int, float]:
    """Item count and cost estimate for ``--dry-run``. No model calls."""
    if config.rq == "rq1":
        return dry_run_summary(
            dataset=dataset, config=config, prices=prices, clients=[GoldSqlStub()]
        )
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    chat = GoldSqlStub()
    price = price_for(prices, chat.model_id)
    if config.rq == "rq2":
        count = len(sample) * len(DecoyCondition)
        return count, count * estimate_call_cost("x" * 400, price)
    embedders = _embedders(config, models, live=False)
    if config.rq == "rq3":
        count = len(sample) * len(TEMPLATES) * len(embedders) * len(QUERY_MODES) * len(SETTINGS)
        return count, 0.0
    count = len(sample) * (1 + len(TEMPLATES) * len(embedders) * len(TOP_K))
    return count, count * estimate_call_cost("x" * 400, price)


def run_fixture(
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    models: ModelsConfig,
    output_dir: Path,
    cache_path: Path,
) -> Path:
    """Run one RQ on the fixture with stub chat and hash embeddings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if config.rq == "rq1":
        run_rq1(
            dataset=dataset,
            config=config,
            prices=prices,
            clients=[GoldSqlStub()],
            output_dir=output_dir,
            cache_path=cache_path,
            concurrency={"stub": 1},
        )
        _report_binary(output_dir, "RQ1 execution accuracy", "level", [M3_CAVEAT])
        return output_dir
    if config.rq == "rq2":
        return _run_rq2(
            dataset, config, prices, output_dir, cache_path, client=GoldSqlStub(), timeout_s=5
        )
    if config.rq == "rq3":
        return _run_rq3(
            dataset,
            config,
            models,
            output_dir,
            cache_path,
            embedders=_embedders(config, models, live=False),
            embedding_note="Hash embeddings stand in for sentence-transformers on fixture runs.",
        )
    return _run_rq4(
        dataset,
        config,
        prices,
        models,
        output_dir,
        cache_path,
        client=GoldSqlStub(),
        embedders=_embedders(config, models, live=False),
        timeout_s=5,
    )


def run_live(
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    models: ModelsConfig,
    output_dir: Path,
    cache_path: Path,
) -> Path:
    """Run one RQ on a downloaded dataset with configured chat and embedding models."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if config.rq == "rq1":
        clients = _chat_clients(config, models)
        run_rq1(
            dataset=dataset,
            config=config,
            prices=prices,
            clients=clients,
            output_dir=output_dir,
            cache_path=cache_path,
            concurrency={client.provider: 8 for client in clients},
        )
        _report_binary(output_dir, "RQ1 execution accuracy", "level", [M3_CAVEAT])
        return output_dir
    if config.rq == "rq2":
        return _run_rq2(
            dataset,
            config,
            prices,
            output_dir,
            cache_path,
            client=_chat_clients(config, models)[0],
            timeout_s=30,
        )
    embedders = _embedders(config, models, live=True)
    if config.rq == "rq3":
        return _run_rq3(
            dataset,
            config,
            models,
            output_dir,
            cache_path,
            embedders=embedders,
            embedding_note="Local sentence-transformers models named in the run.",
        )
    return _run_rq4(
        dataset,
        config,
        prices,
        models,
        output_dir,
        cache_path,
        client=_chat_clients(config, models)[0],
        embedders=embedders,
        timeout_s=30,
    )


def live_summary(
    dataset: Dataset, config: RunConfig, prices: PricesConfig, models: ModelsConfig
) -> tuple[int, float]:
    """Item count and cost estimate for a live run. Does not call a model."""
    if config.rq == "rq3":
        sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
        embedders = _embedders(config, models, live=True)
        count = len(sample) * len(TEMPLATES) * len(embedders) * len(QUERY_MODES) * len(SETTINGS)
        return count, 0.0
    client = _chat_clients(config, models)[0]
    if config.rq == "rq1":
        return dry_run_summary(dataset=dataset, config=config, prices=prices, clients=[client])
    if config.rq == "rq2":
        return _estimate_schema_calls(dataset, config, prices, client, repeats=len(DecoyCondition))
    embedders = _embedders(config, models, live=True)
    repeats = 1 + len(TEMPLATES) * len(embedders) * len(TOP_K)
    return _estimate_schema_calls(
        dataset, config, prices, client, repeats=repeats, level=MetadataLevel.M2
    )


def _estimate_schema_calls(
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    client: ChatClient,
    *,
    repeats: int,
    level: MetadataLevel = MetadataLevel.M1,
) -> tuple[int, float]:
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    price = price_for(prices, client.model_id)
    total = 0.0
    descriptions = {
        database.db_id: dataset.column_descriptions(database.db_id)
        for database in dataset.databases
    }
    for example in sample:
        schema = build_schema(
            dataset.database(example.db_id),
            level,
            evidence=example.evidence,
            descriptions=descriptions[example.db_id],
        )
        rendered = render_text_to_sql(schema, example.question)
        total += estimate_call_cost(rendered.full_prompt, price) * repeats
    return len(sample) * repeats, total


def _chat_clients(config: RunConfig, models: ModelsConfig) -> list[LangChainChat]:
    specs = [model for model in models.models if model.kind is ModelKind.CHAT]
    named = [model for model in specs if not config.models or model.id in config.models]
    chosen = named or specs
    if not chosen:
        message = "No chat model is configured. Add one to configs/models.yaml."
        raise ValueError(message)
    return [LangChainChat(model.id, model.provider) for model in chosen]


def _run_rq2(
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    output_dir: Path,
    cache_path: Path,
    *,
    client: ChatClient,
    timeout_s: float,
) -> Path:
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    price = price_for(prices, client.model_id)
    _count, estimate = _estimate_schema_calls(
        dataset, config, prices, client, repeats=len(DecoyCondition)
    )
    require_within_budget(estimate, config.budget.max_usd)
    cache = ResponseCache(cache_path)
    started = _now()
    rows: list[dict[str, object]] = []
    recorded: list[dict[str, object]] = []
    skipped: list[int] = []
    descriptions = {
        database.db_id: dataset.column_descriptions(database.db_id)
        for database in dataset.databases
    }
    spent = 0.0
    for example in sample:
        original = dataset.database(example.db_id)
        copy = output_dir / "decoys" / f"{example.question_id}.sqlite"
        try:
            built = build_decoy_database(
                original.sqlite_path,
                copy,
                example.sql,
                FIXTURE_DECOY_SEED + example.question_id,
            )
        except (ValueError, sqlglot.errors.SqlglotError):
            skipped.append(example.question_id)
            copy.unlink(missing_ok=True)
            continue
        recorded.append(
            {
                "question_id": example.question_id,
                "seed": built.seed,
                "source_checksum": built.source_checksum,
                "mapping": built.mapping,
            }
        )
        decoy_names = set(built.mapping.values())
        judged_on = original.model_copy(update={"sqlite_path": built.copy_path})
        for condition in DecoyCondition:
            schema = condition_schema(
                original,
                built.copy_path,
                descriptions[example.db_id],
                built.mapping,
                condition,
            )
            rendered = render_text_to_sql(schema, example.question)
            text, cost = _complete(cache, client, example, rendered.full_prompt, price)
            spent += cost
            predicted = extract_sql(text)
            judgement = judge_execution(judged_on, example.sql, predicted, timeout_s=timeout_s)
            rows.append(
                {
                    "question_id": example.question_id,
                    "difficulty": example.difficulty.value,
                    "condition": condition.value,
                    "model_id": client.model_id,
                    "correct": judgement.correct,
                    "uses_decoy": bool(predicted and uses_decoy(predicted, decoy_names)),
                }
            )
        # Decoy SQLite copies are large; keep only mapping/seed in decoys.json.
        for path in (copy, Path(f"{copy}-journal"), Path(f"{copy}-wal"), Path(f"{copy}-shm")):
            path.unlink(missing_ok=True)
    _write_jsonl(output_dir / "predictions.jsonl", rows)
    _write_json(output_dir / "decoys.json", recorded)
    _write_json(output_dir / "sample.json", [example.question_id for example in sample])
    metrics = _group_mean(rows, "condition", "correct")
    for usage in _group_mean(rows, "condition", "uses_decoy"):
        usage["metric"] = "decoy_usage"
        metrics.append(usage)
    for row in metrics:
        row.setdefault("metric", "ex")
    write_metrics_report(
        output_dir,
        title="RQ2 decoys",
        rows=metrics,
        label_column="label",
        value_column="estimate",
        caveats=[
            "Decoy tables exist only on copies. Checksums are in decoys.json.",
            f"{len(skipped)} examples skipped: gold SQL named no local table.",
        ],
    )
    write_manifest(
        output_dir,
        {
            "run_id": output_dir.name,
            "model_ids": [client.model_id],
            "template_versions": [],
            "dataset_checksum": dataset_checksum(dataset),
            "sample_ids_file": "sample.json",
            "seed": config.sample.seed,
            "decoy_seed": FIXTURE_DECOY_SEED,
            "skipped_question_ids": skipped,
            "started_at": started,
            "ended_at": _now(),
            "token_usage": {"input_tokens": 0, "output_tokens": 0},
            "cost_usd": spent,
            "rq": "rq2",
            "estimated_usd": estimate,
            "item_count": len(rows),
        },
    )
    return output_dir


def _run_rq3(
    dataset: Dataset,
    config: RunConfig,
    models: ModelsConfig,
    output_dir: Path,
    cache_path: Path,
    *,
    embedders: list[Embedder],
    embedding_note: str,
) -> Path:
    del models
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    started = _now()
    failures = 0
    rows: list[dict[str, object]] = []
    databases = {database.db_id: database for database in dataset.databases}
    by_template: dict[str, dict[str, tuple[Document, ...]]] = {
        template: {} for template in TEMPLATES
    }
    for database in databases.values():
        descriptions = dataset.column_descriptions(database.db_id)
        for template in TEMPLATES:
            by_template[template][database.db_id] = build_corpus(database, descriptions, template)
    global_corpus = {
        template: tuple(
            document for grouped in by_template[template].values() for document in grouped
        )
        for template in TEMPLATES
    }
    cache_dir = cache_path.parent / "embedding_cache"
    for example in sample:
        database = databases[example.db_id]
        relevance = extract_relevance(example.sql, database)
        if relevance is None:
            failures += 1
            continue
        for template in TEMPLATES:
            for setting in SETTINGS:
                documents = (
                    global_corpus[template]
                    if setting == "global"
                    else by_template[template][example.db_id]
                )
                texts = [document.text for document in documents]
                digest = corpus_hash(documents)
                for embedder in embedders:
                    vectors = cached_embed(embedder, template, digest, texts, cache_dir)
                    for mode in QUERY_MODES:
                        query = example.question
                        if mode == "question_evidence":
                            query = f"{example.question}\n{example.evidence}"
                        query_vector = embedder.embed([query])[0]
                        ranked = rank_documents(query_vector, documents, vectors)
                        columns = [item.identifier for item in ranked if item.kind == "column"]
                        tables = [item.identifier for item in ranked if item.kind == "table"]
                        rows.append(
                            {
                                "question_id": example.question_id,
                                "template": template,
                                "model_id": embedder.model_id,
                                "setting": setting,
                                "query": mode,
                                "recall_at_5": recall_at_k(relevance.columns, columns, 5),
                                "recall_at_10": recall_at_k(relevance.columns, columns, 10),
                                "full_coverage_at_10": full_coverage_at_k(
                                    relevance.columns, columns, 10
                                ),
                                "mrr": reciprocal_rank(relevance.tables, tables),
                                "ndcg_at_10": ndcg_at_k(relevance.columns, columns, 10),
                            }
                        )
    _write_jsonl(output_dir / "predictions.jsonl", rows)
    _write_json(output_dir / "sample.json", [example.question_id for example in sample])
    metrics = _group_mean_multi(
        rows,
        ("template", "model_id", "setting", "query"),
        "recall_at_10",
    )
    write_metrics_report(
        output_dir,
        title="RQ3 schema retrieval",
        rows=metrics,
        label_column="label",
        value_column="estimate",
        caveats=[
            f"Relevance extraction failed on {failures} examples; they are excluded.",
            embedding_note,
        ],
    )
    write_manifest(
        output_dir,
        {
            "run_id": output_dir.name,
            "model_ids": [embedder.model_id for embedder in embedders],
            "template_versions": list(TEMPLATES),
            "dataset_checksum": dataset_checksum(dataset),
            "sample_ids_file": "sample.json",
            "seed": config.sample.seed,
            "started_at": started,
            "ended_at": _now(),
            "token_usage": {"input_tokens": 0, "output_tokens": 0},
            "cost_usd": 0.0,
            "rq": "rq3",
            "estimated_usd": 0.0,
            "item_count": len(rows),
            "relevance_failures": failures,
        },
    )
    _ = cache_path
    return output_dir


def _run_rq4(
    dataset: Dataset,
    config: RunConfig,
    prices: PricesConfig,
    models: ModelsConfig,
    output_dir: Path,
    cache_path: Path,
    *,
    client: ChatClient,
    embedders: list[Embedder],
    timeout_s: float,
) -> Path:
    del models
    sample = stratified_sample(dataset.examples, config.sample.n, config.sample.seed)
    price = price_for(prices, client.model_id)
    repeats = 1 + len(TEMPLATES) * len(embedders) * len(TOP_K)
    _count, estimate = _estimate_schema_calls(
        dataset, config, prices, client, repeats=repeats, level=MetadataLevel.M2
    )
    require_within_budget(estimate, config.budget.max_usd)
    cache = ResponseCache(cache_path)
    started = _now()
    rows: list[dict[str, object]] = []
    descriptions = {
        database.db_id: dataset.column_descriptions(database.db_id)
        for database in dataset.databases
    }
    corpora: dict[tuple[str, str], tuple[Document, ...]] = {}
    for database in dataset.databases:
        for template in TEMPLATES:
            corpora[(database.db_id, template)] = build_corpus(
                database,
                descriptions[database.db_id],
                template,
            )
    cache_dir = cache_path.parent / "embedding_cache"
    prompts: list[tuple[Example, str, str]] = []
    for example in sample:
        database = dataset.database(example.db_id)
        full = build_schema(
            database,
            MetadataLevel.M2,
            descriptions=descriptions[example.db_id],
        )
        prompts.append((example, "full-m2", render_text_to_sql(full, example.question).full_prompt))
        for template in TEMPLATES:
            documents = corpora[(example.db_id, template)]
            texts = [document.text for document in documents]
            digest = corpus_hash(documents)
            for embedder in embedders:
                vectors = cached_embed(embedder, template, digest, texts, cache_dir)
                query_vector = embedder.embed([example.question])[0]
                ranked = rank_documents(query_vector, documents, vectors)
                columns = [item.identifier for item in ranked if item.kind == "column"]
                for k in TOP_K:
                    schema = build_retrieved_m2(
                        database,
                        descriptions[example.db_id],
                        set(columns[:k]),
                    )
                    label = f"{template}-{embedder.model_id}-k{k}"
                    prompts.append(
                        (example, label, render_text_to_sql(schema, example.question).full_prompt)
                    )
    spent_box = [0.0]
    spent_lock = threading.Lock()

    def _one(item: tuple[Example, str, str]) -> dict[str, object] | None:
        example, label, full_prompt = item
        with spent_lock:
            if config.budget.max_usd > 0 and spent_box[0] >= config.budget.max_usd:
                return None
        text, cost = _complete(cache, client, example, full_prompt, price)
        with spent_lock:
            spent_box[0] += cost
        judgement = judge_execution(
            dataset.database(example.db_id),
            example.sql,
            extract_sql(text),
            timeout_s=timeout_s,
        )
        return _ex_row(example.question_id, label, judgement.correct)

    workers = 1 if client.provider == "stub" else 8
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(_one, prompts):
            if row is not None:
                rows.append(row)
    spent = spent_box[0]
    _write_jsonl(output_dir / "predictions.jsonl", rows)
    _write_json(output_dir / "sample.json", [example.question_id for example in sample])
    write_metrics_report(
        output_dir,
        title="RQ4 retrieved schema",
        rows=_group_mean(rows, "condition", "correct"),
        label_column="label",
        value_column="estimate",
        caveats=["The full-schema M2 row is the upper reference for the retrieved-column prompts."],
    )
    write_manifest(
        output_dir,
        {
            "run_id": output_dir.name,
            "model_ids": [client.model_id, *[embedder.model_id for embedder in embedders]],
            "template_versions": list(TEMPLATES),
            "dataset_checksum": dataset_checksum(dataset),
            "sample_ids_file": "sample.json",
            "seed": config.sample.seed,
            "started_at": started,
            "ended_at": _now(),
            "token_usage": {"input_tokens": 0, "output_tokens": 0},
            "cost_usd": spent,
            "rq": "rq4",
            "estimated_usd": estimate,
            "item_count": len(rows),
        },
    )
    return output_dir


def rebuild_report(output_dir: Path) -> None:
    """Regenerate metrics, the plot, and ``report.md`` from ``predictions.jsonl``."""
    manifest = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    rq = str(manifest["rq"])
    if rq == "rq1":
        _report_binary(output_dir, "RQ1 execution accuracy", "level", [M3_CAVEAT])
        return
    if rq == "rq3":
        rows = read_jsonl(output_dir / "predictions.jsonl")
        metrics = _group_mean_multi(
            rows, ("template", "model_id", "setting", "query"), "recall_at_10"
        )
        write_metrics_report(
            output_dir,
            title="RQ3 schema retrieval",
            rows=metrics,
            label_column="label",
            value_column="estimate",
            caveats=["Regenerated from predictions.jsonl."],
        )
        return
    group = "condition"
    title = "RQ2 decoys" if rq == "rq2" else "RQ4 retrieved schema"
    caveats = ["Regenerated from predictions.jsonl."]
    _report_binary(output_dir, title, group, caveats)


def _report_binary(output_dir: Path, title: str, group: str, caveats: list[str]) -> None:
    predictions = read_jsonl(output_dir / "predictions.jsonl")
    rows = _group_mean(predictions, group, "correct")
    write_metrics_report(
        output_dir,
        title=title,
        rows=rows,
        label_column="label",
        value_column="estimate",
        caveats=caveats,
    )


def _group_mean(rows: list[dict[str, object]], group: str, value: str) -> list[dict[str, object]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        buckets[str(row[group])].append(1.0 if row[value] else 0.0)
    metrics: list[dict[str, object]] = []
    for label, values in sorted(buckets.items()):
        interval = bootstrap_mean_ci(values)
        metrics.append(
            {
                "label": label,
                "condition": label,
                "estimate": interval.estimate,
                "low": interval.low,
                "high": interval.high,
                "n": len(values),
            }
        )
    return metrics


def _group_mean_multi(
    rows: list[dict[str, object]],
    keys: tuple[str, ...],
    value: str,
) -> list[dict[str, object]]:
    buckets: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for row in rows:
        identity = tuple(str(row[key]) for key in keys)
        raw = row[value]
        if not isinstance(raw, int | float):
            message = f"{value} must be numeric"
            raise TypeError(message)
        buckets[identity].append(float(raw))
    metrics: list[dict[str, object]] = []
    for identity, values in sorted(buckets.items()):
        interval = bootstrap_mean_ci(values)
        label = " ".join(identity)
        metrics.append(
            {
                "label": label,
                "estimate": interval.estimate,
                "low": interval.low,
                "high": interval.high,
                "n": len(values),
            }
        )
    return metrics


def _complete(
    cache: ResponseCache,
    client: ChatClient,
    example: Example,
    full_prompt: str,
    price: TokenPrice,
) -> tuple[str, float]:
    request_hash = cache.request_hash(client.model_id, PROMPT_VERSION, full_prompt)
    hit = cache.get(request_hash)
    if hit is not None:
        return hit.text, 0.0
    fresh = client.complete(full_prompt, example=example)
    cache.put(request_hash, CachedCompletion(fresh.text, fresh.input_tokens, fresh.output_tokens))
    return fresh.text, call_cost(fresh.input_tokens, fresh.output_tokens, price)


def _embedders(config: RunConfig, models: ModelsConfig, *, live: bool) -> list[Embedder]:
    embedding_ids = [model.id for model in models.models if model.kind is ModelKind.EMBEDDING]
    named = [model_id for model_id in config.models if model_id in embedding_ids]
    ids = named or embedding_ids
    if live:
        return [SentenceTransformerEmbedder(model_id) for model_id in ids]
    return [HashEmbedder(model_id) for model_id in ids]


def _ex_row(question_id: int, condition: str, correct: bool) -> dict[str, object]:
    return {"question_id": question_id, "condition": condition, "correct": correct}


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()
