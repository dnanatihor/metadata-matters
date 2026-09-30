"""Gold columns and tables, qualified against the SQLite schema with sqlglot."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from mm.data.bird import Database, open_readonly


@dataclass(frozen=True)
class Relevance:
    """Tables and ``table.column`` identifiers referenced by one gold query."""

    tables: tuple[str, ...]
    columns: tuple[str, ...]


def extract_relevance(sql: str, database: Database) -> Relevance | None:
    """Qualify ``sql`` and read its tables and columns. ``None`` means failure."""
    try:
        expression = sqlglot.parse_one(sql, read="sqlite")
        qualified = qualify(
            expression,
            schema=sqlite_schema(database),
            dialect="sqlite",
            validate_qualify_columns=False,
        )
    except (sqlglot.errors.SqlglotError, sqlglot.errors.OptimizeError, ValueError):
        return None
    if qualified is None:
        return None
    tables: list[str] = []
    columns: list[str] = []
    cte_names = {cte.alias for cte in qualified.find_all(exp.CTE)}
    aliases: dict[str, str] = {}
    for table in qualified.find_all(exp.Table):
        if not table.name or table.name in cte_names:
            continue
        aliases[table.alias or table.name] = table.name
        if table.name not in tables:
            tables.append(table.name)
    for column in qualified.find_all(exp.Column):
        if not column.table or not column.name or column.table in cte_names:
            continue
        table_name = aliases.get(column.table, column.table)
        label = f"{table_name}.{column.name}"
        if label not in columns:
            columns.append(label)
    if not tables and not columns:
        return None
    return Relevance(tables=tuple(tables), columns=tuple(columns))


def sqlite_schema(database: Database) -> dict[str, object]:
    """sqlglot schema mapping of table to column types."""
    schema: dict[str, object] = {}
    with open_readonly(database.sqlite_path) as connection:
        query = (
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_rows = connection.execute(query).fetchall()
        for table_row in table_rows:
            table = str(table_row["name"])
            columns: dict[str, str] = {}
            info = connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
            for column in info:
                declared = str(column["type"]) or "TEXT"
                columns[str(column["name"])] = declared
            schema[table] = columns
    return schema


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
