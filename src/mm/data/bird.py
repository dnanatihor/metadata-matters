"""Load a dataset stored in the public BIRD dev layout.

The committed fixture uses this same layout and this same loader. A database
is a directory named by ``db_id`` containing ``<db_id>.sqlite`` and
``database_description/<table>.csv`` files with the BIRD columns
``original_column_name``, ``column_name``, ``column_description``,
``data_format``, and ``value_description``.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DESCRIPTION_COLUMNS = (
    "original_column_name",
    "column_name",
    "column_description",
    "data_format",
    "value_description",
)


class Difficulty(StrEnum):
    """BIRD example difficulty."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    CHALLENGING = "challenging"


class Example(BaseModel):
    """One text-to-SQL example from ``dev.json``."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    question_id: int
    db_id: str
    question: str
    evidence: str = ""
    sql: str = Field(alias="SQL")
    difficulty: Difficulty

    @field_validator("evidence", mode="before")
    @classmethod
    def _blank_evidence(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    @field_validator("question", "sql")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if value.strip() == "":
            message = "question and SQL must be non-empty"
            raise ValueError(message)
        return value


class ColumnDescription(BaseModel):
    """One row of a BIRD ``database_description`` CSV."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table_name: str
    original_column_name: str
    column_name: str
    column_description: str
    data_format: str
    value_description: str


class Database(BaseModel):
    """Paths for one SQLite database and its description directory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_id: str
    sqlite_path: Path
    description_dir: Path


class Dataset(BaseModel):
    """Examples and databases loaded from one BIRD-layout root."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root: Path
    examples: tuple[Example, ...]
    databases: tuple[Database, ...]

    def database(self, db_id: str) -> Database:
        for database in self.databases:
            if database.db_id == db_id:
                return database
        message = f"Unknown db_id {db_id!r} under {self.root}"
        raise KeyError(message)

    def column_descriptions(self, db_id: str) -> tuple[ColumnDescription, ...]:
        return read_column_descriptions(self.database(db_id))


def open_readonly(sqlite_path: Path) -> sqlite3.Connection:
    """Open a SQLite file with ``mode=ro``. Writes raise ``OperationalError``."""
    uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def sqlite_table_names(database: Database) -> tuple[str, ...]:
    """Return user table names from the SQLite schema, in schema order."""
    with open_readonly(database.sqlite_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    return tuple(str(row["name"]) for row in rows)


def read_column_descriptions(database: Database) -> tuple[ColumnDescription, ...]:
    """Read every ``database_description/*.csv`` for one database."""
    directory = database.description_dir
    if not directory.is_dir():
        message = f"Missing description directory: {directory}"
        raise FileNotFoundError(message)
    paths = sorted(path for path in directory.glob("*.csv") if path.is_file())
    if not paths:
        message = f"No description CSVs in {directory}"
        raise FileNotFoundError(message)
    rows: list[ColumnDescription] = []
    for path in paths:
        rows.extend(_read_description_csv(path))
    return tuple(rows)


def load_bird_layout(root: Path) -> Dataset:
    """Load ``dev.json`` plus ``dev_databases/<db_id>/`` from ``root``."""
    root = root.resolve()
    dev_json = root / "dev.json"
    if not dev_json.is_file():
        message = f"Missing dev.json: {dev_json}"
        raise FileNotFoundError(message)
    payload = json.loads(dev_json.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        message = f"dev.json must be a list: {dev_json}"
        raise ValueError(message)
    examples = tuple(Example.model_validate(item) for item in payload)
    if not examples:
        message = f"dev.json has no examples: {dev_json}"
        raise ValueError(message)

    databases_root = root / "dev_databases"
    if not databases_root.is_dir():
        message = f"Missing dev_databases directory: {databases_root}"
        raise FileNotFoundError(message)

    seen: dict[str, Database] = {}
    for example in examples:
        if example.db_id in seen:
            continue
        seen[example.db_id] = _load_database(databases_root, example.db_id)
    return Dataset(root=root, examples=examples, databases=tuple(seen.values()))


def _load_database(databases_root: Path, db_id: str) -> Database:
    directory = databases_root / db_id
    sqlite_path = directory / f"{db_id}.sqlite"
    description_dir = directory / "database_description"
    if not sqlite_path.is_file():
        message = f"Missing SQLite database for {db_id}: {sqlite_path}"
        raise FileNotFoundError(message)
    if not description_dir.is_dir():
        message = f"Missing description directory for {db_id}: {description_dir}"
        raise FileNotFoundError(message)
    return Database(db_id=db_id, sqlite_path=sqlite_path, description_dir=description_dir)


def _read_description_csv(path: Path) -> tuple[ColumnDescription, ...]:
    text = _read_text(path)
    reader = csv.DictReader(_normalized_csv_lines(text))
    if reader.fieldnames is None:
        message = f"Description CSV has no header: {path}"
        raise ValueError(message)
    fieldnames = [name.strip() for name in reader.fieldnames]
    missing = [name for name in _DESCRIPTION_COLUMNS if name not in fieldnames]
    if missing:
        message = f"Description CSV {path} is missing columns: {', '.join(missing)}"
        raise ValueError(message)
    table_name = path.stem
    rows: list[ColumnDescription] = []
    for raw in reader:
        normalized = {(key or "").strip(): (value or "").strip() for key, value in raw.items()}
        original = normalized.get("original_column_name", "")
        if original == "":
            continue
        rows.append(
            ColumnDescription(
                table_name=table_name,
                original_column_name=original,
                column_name=normalized.get("column_name", ""),
                column_description=normalized.get("column_description", ""),
                data_format=normalized.get("data_format", ""),
                value_description=normalized.get("value_description", ""),
            )
        )
    return tuple(rows)


def _normalized_csv_lines(text: str) -> list[str]:
    return text.splitlines()


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")
