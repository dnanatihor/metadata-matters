"""Phase 4: gold-SQL relevance, hand-computed rankings, and the embedding cache."""

from __future__ import annotations

import math
from pathlib import Path

from mm.data.fixture import load_fixture
from mm.evaluate.relevance import extract_relevance
from mm.evaluate.retrieval_metrics import (
    full_coverage_at_k,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mm.retrieval.corpus import Document, build_corpus, corpus_hash, filter_corpus, render_template
from mm.retrieval.embed import HashEmbedder, cached_embed
from mm.retrieval.index import rank_documents


def test_relevance_extraction_on_fixture_gold_sql() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    simple = extract_relevance("SELECT country FROM authors WHERE name = 'Ada Okonkwo'", database)
    assert simple is not None
    assert simple.tables == ("authors",)
    assert set(simple.columns) == {"authors.country", "authors.name"}
    joined = dataset.examples[7]
    relevance = extract_relevance(joined.sql, database)
    assert relevance is not None
    assert set(relevance.tables) == {"authors", "books"}
    assert "books.title" in relevance.columns
    assert "authors.country" in relevance.columns
    assert extract_relevance("this is not sql ???", database) is None


def test_metrics_match_hand_computed_rankings() -> None:
    gold_columns = ["c0", "c1"]
    ranking = ["c2", "c0", "c1", "c3"]
    assert recall_at_k(gold_columns, ranking, 2) == 0.5
    assert recall_at_k(gold_columns, ranking, 5) == 1.0
    assert full_coverage_at_k(gold_columns, ranking, 2) == 0.0
    assert full_coverage_at_k(gold_columns, ranking, 3) == 1.0
    # First gold table is at rank 2.
    assert reciprocal_rank(["books"], ["loans", "books", "authors"]) == 0.5
    # Binary nDCG@2: rank1 irrelevant, rank2 relevant.
    # DCG = 1/log2(3). IDCG = 1/log2(2) + 1/log2(3).
    expected = (1 / math.log2(3)) / (1 + 1 / math.log2(3))
    assert ndcg_at_k(gold_columns, ranking, 2) == expected


def test_embedding_cache_skips_the_second_call(tmp_path: Path) -> None:
    embedder = HashEmbedder("sentence-transformers/all-MiniLM-L6-v2")
    texts = ["authors.name", "books.title"]
    first = cached_embed(embedder, "t0", "corpus-hash", texts, tmp_path)
    assert embedder.calls == 1
    second = cached_embed(embedder, "t0", "corpus-hash", texts, tmp_path)
    assert embedder.calls == 1
    assert first.shape == second.shape
    assert (first == second).all()
    other = HashEmbedder("sentence-transformers/all-mpnet-base-v2")
    cached_embed(other, "t0", "corpus-hash", texts, tmp_path)
    assert other.calls == 1
    assert embedder.calls == 1


def test_templates_and_in_database_filter(tmp_path: Path) -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    assert render_template("t0", table="authors", column="name") == "authors.name"
    documents = build_corpus(database, dataset.column_descriptions("tiny_library"), "t4")
    column = next(document for document in documents if document.identifier == "authors.name")
    assert "authors.name" in column.text
    assert "country" in column.text
    extra = Document(db_id="other", kind="column", identifier="other.id", text="other.id")
    scoped = filter_corpus([*documents, extra], "in_database", "tiny_library")
    assert all(document.db_id == "tiny_library" for document in scoped)
    assert len(filter_corpus([*documents, extra], "global", "tiny_library")) == len(documents) + 1
    vectors = cached_embed(
        HashEmbedder("m"),
        "t0",
        corpus_hash(documents),
        [document.text for document in documents],
        tmp_path,
    )
    ranked = rank_documents(vectors[0], documents, vectors)
    assert ranked[0].identifier == documents[0].identifier
