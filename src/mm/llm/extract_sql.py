"""Pull the SQL query out of a model response."""

from __future__ import annotations

import re

_FENCE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(response: str) -> str | None:
    """Return the last fenced ``sql`` block, or the whole response if none.

    An empty response, or an empty fenced block, is an extraction failure.
    """
    if response.strip() == "":
        return None
    matches = [match.strip() for match in _FENCE.findall(response)]
    if matches:
        chosen = matches[-1]
        return chosen if chosen else None
    return response.strip()
