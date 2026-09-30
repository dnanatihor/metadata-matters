"""Phase 1: context levels, SQL extraction, and execution accuracy on the fixture."""

from __future__ import annotations

from mm.context.levels import MetadataLevel, build_schema, truncate_sample
from mm.data.fixture import load_fixture
from mm.evaluate.execution import execution_accuracy, judge_execution
from mm.llm.extract_sql import extract_sql
from mm.prompt import PROMPT_VERSION, render_text_to_sql

RUNAWAY_SQL = (
    "WITH RECURSIVE c(x) AS ("
    "SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 100000000"
    ") SELECT x FROM c"
)


def test_extract_sql_uses_last_fence_or_whole_response() -> None:
    assert extract_sql("```sql\nSELECT 1\n```\n```sql\nSELECT 2\n```") == "SELECT 2"
    assert extract_sql("SELECT title FROM books") == "SELECT title FROM books"
    assert extract_sql("   ") is None
    assert extract_sql("```sql\n   \n```") is None


def test_prompt_is_sqlite_with_fenced_sql_instruction() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    schema = build_schema(database, MetadataLevel.M0)
    rendered = render_text_to_sql(schema, "How many authors?")
    assert rendered.temperature == 0
    assert "SQLite" in rendered.system
    assert "sql" in rendered.system
    assert schema in rendered.system
    assert rendered.user == "How many authors?"
    assert PROMPT_VERSION == "text_to_sql.v1"


def test_metadata_levels_add_descriptions_samples_and_evidence() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    descriptions = dataset.column_descriptions("tiny_library")
    example = dataset.examples[3]
    m0 = build_schema(database, MetadataLevel.M0, descriptions=descriptions)
    m1 = build_schema(database, MetadataLevel.M1, descriptions=descriptions)
    m2 = build_schema(
        database, MetadataLevel.M2, descriptions=descriptions, evidence=example.evidence
    )
    m3 = build_schema(
        database,
        MetadataLevel.M3,
        descriptions=descriptions,
        evidence=example.evidence,
    )
    assert "CREATE TABLE authors" in m0
    assert "CREATE TABLE books" in m0
    assert "CREATE TABLE loans" in m0
    assert "-- country:" not in m0
    assert "-- country:" in m1
    assert "ISO 3166-1 alpha-2" not in m1
    assert "value description:" in m2
    assert "sample values:" in m2
    assert "BR" in m2
    assert "Business glossary hint:" not in m2
    assert m3.startswith(m2) or "Business glossary hint:" in m3
    assert "Business glossary hint:" in m3
    assert example.evidence in m3
    assert truncate_sample("x" * 50) == "x" * 40


def test_gold_sql_scores_100_percent_and_invalid_sql_scores_0() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    gold = [
        judge_execution(database, example.sql, example.sql, timeout_s=5)
        for example in dataset.examples
    ]
    invalid = [
        judge_execution(database, example.sql, "SELECT no_such_column FROM authors", timeout_s=5)
        for example in dataset.examples
    ]
    missing = [
        judge_execution(database, example.sql, None, timeout_s=5) for example in dataset.examples
    ]
    assert execution_accuracy(gold) == 1.0
    assert all(judgement.cause is None for judgement in gold)
    assert execution_accuracy(invalid) == 0.0
    assert all(
        judgement.cause is not None and judgement.cause.startswith("error:")
        for judgement in invalid
    )
    assert execution_accuracy(missing) == 0.0
    assert all(judgement.cause == "extract_failed" for judgement in missing)


def test_same_rows_in_a_different_order_are_correct() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    gold = "SELECT title FROM books"
    reordered = "SELECT title FROM books ORDER BY title COLLATE BINARY DESC"
    judgement = judge_execution(database, gold, reordered, timeout_s=5)
    assert judgement.correct
    assert judgement.cause is None


def test_runaway_query_times_out_and_is_incorrect() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    gold = dataset.examples[0].sql
    judgement = judge_execution(database, gold, RUNAWAY_SQL, timeout_s=0.2)
    assert judgement.correct is False
    assert judgement.cause == "timeout"
