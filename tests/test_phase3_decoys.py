"""Phase 3: decoy copies, rewritten gold SQL, and decoy-usage detection."""

from __future__ import annotations

from pathlib import Path

from mm.data.bird import Database
from mm.data.fixture import load_fixture
from mm.decoys import (
    FIXTURE_DECOY_SEED,
    DecoyCondition,
    build_decoy_database,
    condition_schema,
    file_checksum,
    referenced_tables,
    rewrite_tables,
    uses_decoy,
)
from mm.evaluate.execution import execute_query


def test_decoy_usage_detection() -> None:
    decoys = {"authors_legacy", "books_v1"}
    assert uses_decoy("SELECT * FROM authors_legacy", decoys)
    assert uses_decoy("SELECT b.title FROM books_v1 AS b", decoys)
    assert uses_decoy("SELECT title FROM books", decoys) is False
    assert referenced_tables(
        "SELECT a.name FROM authors AS a JOIN books AS b ON a.author_id = b.author_id"
    ) == (
        "authors",
        "books",
    )


def test_original_checksum_is_unchanged_and_rewritten_sql_usually_differs(tmp_path: Path) -> None:
    dataset = load_fixture()
    source = dataset.database("tiny_library").sqlite_path
    before = file_checksum(source)
    descriptions = dataset.column_descriptions("tiny_library")
    differed = 0
    for example in dataset.examples:
        built = build_decoy_database(
            source,
            tmp_path / f"{example.question_id}.sqlite",
            example.sql,
            FIXTURE_DECOY_SEED + example.question_id,
        )
        assert file_checksum(source) == before == built.source_checksum
        rewritten = rewrite_tables(example.sql, built.mapping)
        original = execute_query(_database(source), example.sql, timeout_s=5)
        decoy = execute_query(_database(built.copy_path), rewritten, timeout_s=5)
        assert original.rows is not None
        assert decoy.cause != "timeout"
        if original.rows != decoy.rows:
            differed += 1
        schema = condition_schema(
            _database(source),
            built.copy_path,
            descriptions,
            built.mapping,
            DecoyCondition.D2,
        )
        assert "-- status: certified" in schema
        assert "-- status: deprecated" in schema
        assert "Deprecated; use `" in schema
    assert differed / len(dataset.examples) >= 0.95


def _database(path: Path) -> Database:
    return Database(
        db_id="tiny_library",
        sqlite_path=path,
        description_dir=path.parent / "database_description",
    )
