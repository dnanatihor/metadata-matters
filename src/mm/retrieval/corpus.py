"""One document per column and one per table, rendered from versioned templates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from mm.context.levels import truncate_sample
from mm.data.bird import ColumnDescription, Database, open_readonly
from mm.paths import repo_root

TEMPLATES = ("t0", "t1", "t2", "t3", "t4")


@dataclass(frozen=True)
class Document:
    db_id: str
    kind: str
    identifier: str
    text: str


def render_template(template: str, **values: str) -> str:
    path = _template_path(template)
    environment = Environment(
        undefined=StrictUndefined, autoescape=False, keep_trailing_newline=False
    )
    return environment.from_string(path.read_text(encoding="utf-8")).render(**values).strip()


def build_corpus(
    database: Database,
    descriptions: tuple[ColumnDescription, ...],
    template: str,
    *,
    table_description: str = "",
) -> tuple[Document, ...]:
    """Column and table documents for one database and one embedding template."""
    if template not in TEMPLATES:
        message = f"Unknown embedding template {template}"
        raise ValueError(message)
    grouped: dict[str, list[ColumnDescription]] = {}
    for description in descriptions:
        grouped.setdefault(description.table_name, []).append(description)
    samples = _samples(database, grouped)
    documents: list[Document] = []
    for table, columns in sorted(grouped.items()):
        siblings = ", ".join(sorted(column.original_column_name for column in columns))
        documents.append(
            Document(
                db_id=database.db_id,
                kind="table",
                identifier=table,
                text=table if table_description == "" else f"{table} {table_description}",
            )
        )
        for column in columns:
            values = " | ".join(samples.get((table, column.original_column_name), ()))
            text = render_template(
                template,
                table=table,
                column=column.original_column_name,
                data_type=column.data_format,
                column_description=column.column_description,
                value_description=column.value_description,
                sample_values=values,
                table_description=table_description,
                sibling_columns=siblings,
            )
            documents.append(
                Document(
                    db_id=database.db_id,
                    kind="column",
                    identifier=f"{table}.{column.original_column_name}",
                    text=text,
                )
            )
    return tuple(documents)


def filter_corpus(
    documents: tuple[Document, ...] | list[Document], setting: str, db_id: str
) -> tuple[Document, ...]:
    if setting == "global":
        return tuple(documents)
    if setting != "in_database":
        message = f"Unknown retrieval setting {setting}"
        raise ValueError(message)
    return tuple(document for document in documents if document.db_id == db_id)


def corpus_hash(documents: tuple[Document, ...] | list[Document]) -> str:
    digest = hashlib.sha256()
    for document in documents:
        digest.update(document.identifier.encode())
        digest.update(b"\0")
        digest.update(document.text.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _template_path(template: str) -> Path:
    return repo_root() / "templates" / "embedding" / f"{template}.j2"


def _samples(
    database: Database,
    grouped: dict[str, list[ColumnDescription]],
) -> dict[tuple[str, str], tuple[str, ...]]:
    found: dict[tuple[str, str], tuple[str, ...]] = {}
    with open_readonly(database.sqlite_path) as connection:
        for table, columns in grouped.items():
            for column in columns:
                name = column.original_column_name
                quoted_table = _quote(table)
                quoted_column = _quote(name)
                query = (
                    f"SELECT DISTINCT {quoted_column} FROM {quoted_table} "
                    f"WHERE {quoted_column} IS NOT NULL ORDER BY 1 LIMIT 3"
                )
                rows = connection.execute(query).fetchall()
                found[(table, name)] = tuple(truncate_sample(row[0]) for row in rows)
    return found


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
