"""Phase 0: the fixture loads through the same loader as a BIRD layout."""

from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from mm.data.bird import Difficulty, load_bird_layout, open_readonly, sqlite_table_names
from mm.data.fixture import load_fixture

EXPECTED_TABLES = frozenset({"authors", "books", "loans"})


def test_fixture_has_twelve_questions_and_three_tables() -> None:
    dataset = load_fixture()
    assert len(dataset.examples) == 12
    assert {example.db_id for example in dataset.examples} == {"tiny_library"}
    counts = Counter(example.difficulty for example in dataset.examples)
    assert counts == {
        Difficulty.SIMPLE: 4,
        Difficulty.MODERATE: 4,
        Difficulty.CHALLENGING: 4,
    }
    database = dataset.database("tiny_library")
    assert set(sqlite_table_names(database)) == EXPECTED_TABLES
    described = {row.table_name for row in dataset.column_descriptions("tiny_library")}
    assert described == EXPECTED_TABLES


def test_fixture_uses_bird_loader() -> None:
    via_fixture = load_fixture()
    via_layout = load_bird_layout(via_fixture.root)
    assert type(via_fixture) is type(via_layout)
    assert [example.model_dump() for example in via_fixture.examples] == [
        example.model_dump() for example in via_layout.examples
    ]
    for example in via_fixture.examples:
        assert example.question.strip()
        assert example.evidence.strip()
        assert example.sql.strip()
        assert example.difficulty in set(Difficulty)


def test_synthetic_bird_layout_uses_same_loader(tmp_path: Path) -> None:
    root = tmp_path / "bird"
    db_dir = root / "dev_databases" / "shop"
    desc = db_dir / "database_description"
    desc.mkdir(parents=True)
    (db_dir / "shop.sqlite").write_bytes(_one_table_sqlite())
    _write_description(desc / "items.csv", [("sku", "sku", "stock keeping unit", "text", "")])
    (root / "dev.json").write_text(
        json.dumps(
            [
                {
                    "question_id": 7,
                    "db_id": "shop",
                    "question": "How many items?",
                    "evidence": None,
                    "SQL": "SELECT COUNT(*) FROM items",
                    "difficulty": "simple",
                    "comment": "unknown keys are ignored",
                }
            ]
        ),
        encoding="utf-8",
    )
    dataset = load_bird_layout(root)
    assert type(dataset) is type(load_fixture())
    assert dataset.examples[0].evidence == ""
    assert dataset.examples[0].sql == "SELECT COUNT(*) FROM items"
    assert dataset.database("shop").sqlite_path.name == "shop.sqlite"


def test_column_descriptions_cover_sqlite_columns() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    grouped: dict[str, set[str]] = {name: set() for name in EXPECTED_TABLES}
    for row in dataset.column_descriptions("tiny_library"):
        grouped[row.table_name].add(row.original_column_name)
        assert row.column_description.strip()
    with open_readonly(database.sqlite_path) as connection:
        for table in EXPECTED_TABLES:
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            columns = {str(row["name"]) for row in info}
            assert grouped[table] == columns


def test_readonly_connection_rejects_writes() -> None:
    database = load_fixture().database("tiny_library")
    with open_readonly(database.sqlite_path) as connection, pytest.raises(sqlite3.OperationalError):
        connection.execute("CREATE TABLE should_fail (id INTEGER)")


def test_gold_sql_executes() -> None:
    dataset = load_fixture()
    database = dataset.database("tiny_library")
    with open_readonly(database.sqlite_path) as connection:
        for example in dataset.examples:
            rows = connection.execute(example.sql).fetchall()
            assert rows, example.question_id


def test_cp1252_description_with_padded_headers(tmp_path: Path) -> None:
    root = tmp_path / "bird"
    db_dir = root / "dev_databases" / "notes"
    desc = db_dir / "database_description"
    desc.mkdir(parents=True)
    (db_dir / "notes.sqlite").write_bytes(_one_table_sqlite(table="notes", column="body"))
    raw = (
        b" original_column_name , column_name , column_description ,"
        b" data_format , value_description \n"
        b"body,body,caf\x92 note,text,\n"
    )
    (desc / "notes.csv").write_bytes(raw)
    (root / "dev.json").write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "notes",
                    "question": "List notes",
                    "evidence": "body text",
                    "SQL": "SELECT body FROM notes",
                    "difficulty": "simple",
                }
            ]
        ),
        encoding="utf-8",
    )
    descriptions = load_bird_layout(root).column_descriptions("notes")
    assert descriptions[0].original_column_name == "body"
    assert descriptions[0].column_description == "caf\u2019 note"


def _write_description(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "original_column_name",
                "column_name",
                "column_description",
                "data_format",
                "value_description",
            ]
        )
        writer.writerows(rows)


def _one_table_sqlite(table: str = "items", column: str = "sku") -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        connection = sqlite3.connect(path)
        connection.execute(f"CREATE TABLE {table} ({column} TEXT)")
        connection.execute(f"INSERT INTO {table} ({column}) VALUES ('a')")
        connection.commit()
        connection.close()
        return path.read_bytes()
