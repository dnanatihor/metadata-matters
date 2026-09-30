"""CREATE TABLE statements read from a SQLite schema."""

from __future__ import annotations

from mm.data.bird import Database, open_readonly


def create_table_statements(database: Database) -> tuple[str, ...]:
    """Return the schema's ``CREATE TABLE`` text, one statement per user table.

    Order is the table name. Read from ``sqlite_master``, not reconstructed.
    """
    with open_readonly(database.sqlite_path) as connection:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY name"
        ).fetchall()
    return tuple(str(row["sql"]).strip() for row in rows)
