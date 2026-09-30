"""Metadata levels M0-M3 for the schema section of the text-to-SQL prompt."""

from __future__ import annotations

from enum import StrEnum

from mm.context.ddl import create_table_statements
from mm.data.bird import ColumnDescription, Database, open_readonly

SAMPLE_LIMIT = 3
SAMPLE_MAX_CHARS = 40


class MetadataLevel(StrEnum):
    """How much catalog metadata is placed in the schema context."""

    M0 = "M0"
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"


def build_schema(
    database: Database,
    level: MetadataLevel,
    *,
    evidence: str = "",
    descriptions: tuple[ColumnDescription, ...] = (),
) -> str:
    """Build the schema section for one metadata level."""
    statements = create_table_statements(database)
    if level is MetadataLevel.M0:
        return "\n\n".join(statements)
    grouped = _group_descriptions(descriptions)
    blocks: list[str] = []
    for statement in statements:
        table = _table_name(statement)
        blocks.append(_annotate_statement(statement, grouped.get(table, ()), level, database))
    schema = "\n\n".join(blocks)
    if level is MetadataLevel.M3:
        schema = f"{schema}\n\nBusiness glossary hint:\n{evidence.strip()}"
    return schema


def truncate_sample(value: object) -> str:
    return str(value)[:SAMPLE_MAX_CHARS]


def _annotate_statement(
    statement: str,
    columns: tuple[ColumnDescription, ...],
    level: MetadataLevel,
    database: Database,
) -> str:
    lines = [statement]
    samples: dict[str, tuple[str, ...]] = {}
    if level in {MetadataLevel.M2, MetadataLevel.M3} and columns:
        table = columns[0].table_name
        samples = _sample_values(
            database, table, tuple(column.original_column_name for column in columns)
        )
    for column in columns:
        description = " ".join(column.column_description.split())
        if description:
            lines.append(f"-- {column.original_column_name}: {description}")
        if level in {MetadataLevel.M2, MetadataLevel.M3}:
            value_description = " ".join(column.value_description.split())
            if value_description:
                lines.append(
                    f"-- {column.original_column_name} value description: {value_description}"
                )
            values = samples.get(column.original_column_name, ())
            if values:
                rendered = " | ".join(values)
                lines.append(f"-- {column.original_column_name} sample values: {rendered}")
    return "\n".join(lines)


def _group_descriptions(
    descriptions: tuple[ColumnDescription, ...],
) -> dict[str, tuple[ColumnDescription, ...]]:
    grouped: dict[str, list[ColumnDescription]] = {}
    for description in descriptions:
        grouped.setdefault(description.table_name, []).append(description)
    return {table: tuple(columns) for table, columns in grouped.items()}


def _table_name(statement: str) -> str:
    marker = "CREATE TABLE "
    start = statement.upper().find(marker)
    if start < 0:
        return ""
    rest = statement[start + len(marker) :].lstrip()
    if rest.startswith(("'", '"', "`", "[")):
        quote = "]" if rest[0] == "[" else rest[0]
        end = rest.find(quote, 1)
        return rest[1:end]
    return rest.split()[0]


def _sample_values(
    database: Database,
    table: str,
    columns: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    with open_readonly(database.sqlite_path) as connection:
        for column in columns:
            query = (
                f"SELECT DISTINCT {_quote(column)} FROM {_quote(table)} "
                f"WHERE {_quote(column)} IS NOT NULL ORDER BY 1 LIMIT {SAMPLE_LIMIT}"
            )
            rows = connection.execute(query).fetchall()
            found[column] = tuple(truncate_sample(row[0]) for row in rows)
    return found


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
