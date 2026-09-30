"""Execution accuracy against a SQLite database.

Correct when the predicted and gold result sets are equal as sets of rows.
Order does not matter. A query that errors, times out, or never yields SQL is
incorrect, and the cause is kept.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from mm.data.bird import Database, open_readonly

DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class QueryOutcome:
    """Rows from one query, or the reason it produced none."""

    rows: frozenset[tuple[object, ...]] | None
    cause: str | None


@dataclass(frozen=True)
class ExecutionJudgement:
    """Whether one prediction matched its gold query."""

    correct: bool
    cause: str | None


def execute_query(
    database: Database, sql: str, *, timeout_s: float = DEFAULT_TIMEOUT_S
) -> QueryOutcome:
    """Run ``sql`` read-only. ``timeout_s`` is enforced with a progress handler."""
    deadline = time.monotonic() + timeout_s
    timed_out = False

    def handler() -> int:
        nonlocal timed_out
        if time.monotonic() >= deadline:
            timed_out = True
            return 1
        return 0

    try:
        with open_readonly(database.sqlite_path) as connection:
            connection.set_progress_handler(handler, 1000)
            try:
                cursor = connection.execute(sql)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                if timed_out or "interrupt" in str(exc).lower():
                    return QueryOutcome(rows=None, cause="timeout")
                return QueryOutcome(rows=None, cause=f"error: {exc}")
    except sqlite3.Error as exc:
        return QueryOutcome(rows=None, cause=f"error: {exc}")
    return QueryOutcome(rows=frozenset(tuple(row) for row in rows), cause=None)


def judge_execution(
    database: Database,
    gold_sql: str,
    predicted_sql: str | None,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ExecutionJudgement:
    """Score one prediction. ``predicted_sql is None`` means extraction failed."""
    if predicted_sql is None or predicted_sql.strip() == "":
        return ExecutionJudgement(correct=False, cause="extract_failed")
    gold = execute_query(database, gold_sql, timeout_s=timeout_s)
    if gold.rows is None:
        return ExecutionJudgement(correct=False, cause=f"gold {gold.cause}")
    predicted = execute_query(database, predicted_sql, timeout_s=timeout_s)
    if predicted.rows is None:
        return ExecutionJudgement(correct=False, cause=predicted.cause)
    if predicted.rows == gold.rows:
        return ExecutionJudgement(correct=True, cause=None)
    return ExecutionJudgement(correct=False, cause="result_mismatch")


def execution_accuracy(judgements: list[ExecutionJudgement]) -> float:
    """Fraction correct. An empty list is 0."""
    if not judgements:
        return 0.0
    return sum(1 for judgement in judgements if judgement.correct) / len(judgements)
