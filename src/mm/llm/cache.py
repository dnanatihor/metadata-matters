"""SQLite cache of model responses, keyed by request hash."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CachedCompletion:
    text: str
    input_tokens: int
    output_tokens: int


class ResponseCache:
    """Process-safe cache. A hit means the model is not called again."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    request_hash TEXT PRIMARY KEY,
                    response_text TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL
                )
                """
            )

    def request_hash(self, model_id: str, prompt_version: str, full_prompt: str) -> str:
        payload = f"{model_id}|{prompt_version}|{full_prompt}".encode()
        return hashlib.sha256(payload).hexdigest()

    def get(self, request_hash: str) -> CachedCompletion | None:
        with self._lock, self._connect() as connection:
            query = (
                "SELECT response_text, input_tokens, output_tokens "
                "FROM responses WHERE request_hash = ?"
            )
            row = connection.execute(query, (request_hash,)).fetchone()
        if row is None:
            return None
        return CachedCompletion(
            text=str(row[0]), input_tokens=int(row[1]), output_tokens=int(row[2])
        )

    def put(self, request_hash: str, completion: CachedCompletion) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO responses (request_hash, response_text, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_hash) DO NOTHING
                """,
                (
                    request_hash,
                    completion.text,
                    completion.input_tokens,
                    completion.output_tokens,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, check_same_thread=False)
