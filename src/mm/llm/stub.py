"""Chat stub used by ``mm run --fixture``. It returns the example's gold SQL."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from mm.data.bird import Example


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


class GoldSqlStub:
    """Deterministic stand-in for a chat model. Counts how often it is called."""

    model_id = "stub-gold"
    provider = "stub"

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, full_prompt: str, *, example: Example) -> Completion:
        with self._lock:
            self.calls += 1
        sql = example.sql
        text = f"```sql\n{sql}\n```"
        return Completion(
            text=text,
            input_tokens=max(1, len(full_prompt) // 4),
            output_tokens=max(1, len(sql) // 4),
        )
