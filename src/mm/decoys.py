"""RQ2 decoy tables on copies of a SQLite database.

Original files are never opened for writing. Each copy drops 30% of the rows
in one or two gold-SQL tables and scales one numeric column by a seeded factor
in ``[0.8, 1.2)``.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np
import sqlglot
from sqlglot import exp

from mm.context.levels import MetadataLevel, build_schema
from mm.data.bird import ColumnDescription, Database, open_readonly

PATTERNS = ("{name}_legacy", "{name}_v1", "{name}_backup", "old_{name}")
# Base seed for the committed fixture. Per example the generator seed is
# FIXTURE_DECOY_SEED + question_id. Seed 8 is the smallest base at which the
# rewritten gold SQL differs on every fixture example (above the 95% bar).
FIXTURE_DECOY_SEED = 8


class DecoyCondition(StrEnum):
    """Governance-label conditions, all built on M1."""

    D0 = "D0"
    D1 = "D1"
    D2 = "D2"


@dataclass(frozen=True)
class DecoyBuild:
    """A decoy copy and the real-table to decoy-table map that produced it."""

    copy_path: Path
    mapping: dict[str, str]
    seed: int
    source_checksum: str


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if chunk == b"":
                break
            digest.update(chunk)
    return digest.hexdigest()


def referenced_tables(sql: str) -> tuple[str, ...]:
    """Table names in ``sql``, in first-seen order. CTE aliases are omitted."""
    expression = sqlglot.parse_one(sql, read="sqlite")
    cte_names = {cte.alias for cte in expression.find_all(exp.CTE)}
    found: list[str] = []
    for table in expression.find_all(exp.Table):
        name = table.name
        if name and name not in cte_names and name not in found:
            found.append(name)
    return tuple(found)


def rewrite_tables(sql: str, mapping: dict[str, str]) -> str:
    """Replace real table names with decoy names, leaving aliases in place."""
    expression = sqlglot.parse_one(sql, read="sqlite")
    for table in expression.find_all(exp.Table):
        renamed = mapping.get(table.name)
        if renamed is not None:
            table.set("this", exp.to_identifier(renamed))
    return expression.sql(dialect="sqlite")


def uses_decoy(sql: str, decoy_names: set[str]) -> bool:
    """True when ``sqlglot`` finds any decoy table name in ``sql``."""
    try:
        names = set(referenced_tables(sql))
    except sqlglot.errors.SqlglotError:
        return False
    return bool(names & decoy_names)


def build_decoy_database(source: Path, dest: Path, gold_sql: str, seed: int) -> DecoyBuild:
    """Copy ``source`` to ``dest`` and add decoy tables. ``source`` is unchanged."""
    if source.resolve() == dest.resolve():
        message = "decoy copy must not be the original database"
        raise ValueError(message)
    checksum = file_checksum(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    real_tables = _existing_tables(source, referenced_tables(gold_sql))
    chosen = _choose_tables(real_tables, seed)
    mapping = {real: _pattern_name(real, index) for index, real in enumerate(chosen)}
    _populate_decoys(dest, mapping, seed)
    if file_checksum(source) != checksum:
        message = f"original database checksum changed: {source}"
        raise RuntimeError(message)
    return DecoyBuild(
        copy_path=dest,
        mapping=mapping,
        seed=seed,
        source_checksum=checksum,
    )


def condition_schema(
    original: Database,
    decoy_copy: Path,
    descriptions: tuple[ColumnDescription, ...],
    mapping: dict[str, str],
    condition: DecoyCondition,
) -> str:
    """M1 schema for real and decoy tables, plus the condition's labels."""
    m1 = build_schema(original, MetadataLevel.M1, descriptions=descriptions)
    if condition in {DecoyCondition.D1, DecoyCondition.D2}:
        m1 = _label_real_tables(m1, mapping, "-- status: certified")
    decoy_db = Database(
        db_id=original.db_id, sqlite_path=decoy_copy, description_dir=original.description_dir
    )
    decoy_descriptions = _clone_descriptions(descriptions, mapping)
    decoy_m1 = build_schema(decoy_db, MetadataLevel.M1, descriptions=decoy_descriptions)
    decoy_only = _statements_for(decoy_m1, set(mapping.values()))
    if condition is DecoyCondition.D0:
        labeled = decoy_only
    else:
        labeled = _label_block(decoy_only, mapping, condition)
    return f"{m1}\n\n{labeled}"


def _existing_tables(source: Path, names: tuple[str, ...]) -> tuple[str, ...]:
    with open_readonly(source) as connection:
        present = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    return tuple(name for name in names if name in present)


def _choose_tables(tables: tuple[str, ...], seed: int) -> tuple[str, ...]:
    if not tables:
        message = "gold SQL did not reference a table in this database"
        raise ValueError(message)
    if len(tables) <= 2:
        return tables
    rng = np.random.default_rng(seed)
    indexes = sorted(int(value) for value in rng.choice(len(tables), size=2, replace=False))
    return tuple(tables[index] for index in indexes)


def _pattern_name(real: str, index: int) -> str:
    pattern = PATTERNS[index % len(PATTERNS)]
    return pattern.format(name=real)


def _populate_decoys(dest: Path, mapping: dict[str, str], seed: int) -> None:
    rng = np.random.default_rng(seed)
    connection = sqlite3.connect(dest)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = OFF")
    connection.execute("PRAGMA synchronous = OFF")
    try:
        for real, decoy in mapping.items():
            connection.execute(f"CREATE TABLE {_quote(decoy)} AS SELECT * FROM {_quote(real)}")
            _drop_rows(connection, decoy, rng)
            _scale_numeric(connection, decoy, rng)
        connection.commit()
    finally:
        connection.close()


def _drop_rows(connection: sqlite3.Connection, table: str, rng: np.random.Generator) -> None:
    primary = _primary_key(connection, table)
    keys = [row[0] for row in connection.execute(f"SELECT {_quote(primary)} FROM {_quote(table)}")]
    drop_count = int(len(keys) * 0.3)
    if drop_count <= 0 or not keys:
        return
    chosen = rng.choice(len(keys), size=drop_count, replace=False)
    connection.execute("CREATE TEMP TABLE mm_drop (k)")
    connection.executemany(
        "INSERT INTO mm_drop (k) VALUES (?)",
        ((keys[int(index)],) for index in chosen),
    )
    connection.execute(
        f"DELETE FROM {_quote(table)} WHERE {_quote(primary)} IN (SELECT k FROM mm_drop)"
    )
    connection.execute("DROP TABLE mm_drop")


def _scale_numeric(connection: sqlite3.Connection, table: str, rng: np.random.Generator) -> None:
    columns = _numeric_columns(connection, table)
    if not columns:
        return
    column = columns[int(rng.integers(0, len(columns)))]
    factor = float(rng.uniform(0.8, 1.2))
    connection.execute(
        f"UPDATE {_quote(table)} SET {_quote(column)} = {_quote(column)} * ?", (factor,)
    )


def _primary_key(connection: sqlite3.Connection, table: str) -> str:
    rows = list(connection.execute(f"PRAGMA table_info({_quote(table)})"))
    for row in rows:
        if int(row["pk"]) == 1:
            return str(row["name"])
    return str(rows[0]["name"])


def _numeric_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    numeric: list[str] = []
    for row in connection.execute(f"PRAGMA table_info({_quote(table)})"):
        declared = str(row["type"]).upper()
        if any(token in declared for token in ("INT", "REAL", "FLOA", "DOUB", "NUM")):
            numeric.append(str(row["name"]))
    preferred = [name for name in numeric if not name.endswith("_id")]
    chosen = preferred or numeric
    return tuple(chosen)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _clone_descriptions(
    descriptions: tuple[ColumnDescription, ...],
    mapping: dict[str, str],
) -> tuple[ColumnDescription, ...]:
    cloned: list[ColumnDescription] = []
    for description in descriptions:
        decoy = mapping.get(description.table_name)
        if decoy is None:
            continue
        cloned.append(description.model_copy(update={"table_name": decoy}))
    return tuple(cloned)


def _label_real_tables(schema: str, mapping: dict[str, str], label: str) -> str:
    blocks = schema.split("\n\n")
    updated: list[str] = []
    for block in blocks:
        table = _create_table_name(block)
        if table in mapping:
            updated.append(f"{block}\n{label}")
        else:
            updated.append(block)
    return "\n\n".join(updated)


def _statements_for(schema: str, names: set[str]) -> str:
    blocks = [block for block in schema.split("\n\n") if _create_table_name(block) in names]
    return "\n\n".join(blocks)


def _label_block(schema: str, mapping: dict[str, str], condition: DecoyCondition) -> str:
    inverse = {decoy: real for real, decoy in mapping.items()}
    blocks: list[str] = []
    for block in schema.split("\n\n"):
        table = _create_table_name(block)
        real = inverse.get(table, table)
        text = f"{block}\n-- status: deprecated"
        if condition is DecoyCondition.D2:
            text = f"{text}\n-- Deprecated; use `{real}` instead."
        blocks.append(text)
    return "\n\n".join(blocks)


def _create_table_name(statement: str) -> str:
    marker = "CREATE TABLE "
    start = statement.upper().find(marker)
    if start < 0:
        return ""
    rest = statement[start + len(marker) :].lstrip()
    if rest.startswith('"'):
        end = rest.find('"', 1)
        return rest[1:end]
    return rest.split("(", 1)[0].strip().strip('"')
