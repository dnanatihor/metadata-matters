"""Render ``prompts/text_to_sql.v1.md`` into a system message and a user message."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from mm.paths import repo_root

PROMPT_VERSION = "text_to_sql.v1"
DIALECT = "SQLite"
_SPLIT = "===USER==="


class PromptPair:
    """The two messages the runner sends, temperature 0."""

    def __init__(self, system: str, user: str) -> None:
        self.system = system
        self.user = user
        self.temperature = 0

    @property
    def full_prompt(self) -> str:
        return f"{self.system}\n\n{self.user}"


def render_text_to_sql(
    schema: str, question: str, *, prompt_path: Path | None = None
) -> PromptPair:
    path = (
        prompt_path if prompt_path is not None else repo_root() / "prompts" / f"{PROMPT_VERSION}.md"
    )
    system_source, user_source = _split_template(path)
    system = _render(system_source, dialect=DIALECT, schema=schema)
    user = _render(user_source, dialect=DIALECT, question=question)
    return PromptPair(system=system, user=user)


def _split_template(path: Path) -> tuple[str, str]:
    text = _read_prompt(path)
    if not text.startswith("===SYSTEM==="):
        message = f"Prompt must start with ===SYSTEM===: {path}"
        raise ValueError(message)
    body = text[len("===SYSTEM===") :]
    if _SPLIT not in body:
        message = f"Prompt must contain {_SPLIT}: {path}"
        raise ValueError(message)
    system, user = body.split(_SPLIT, maxsplit=1)
    return system.strip("\n"), user.strip("\n")


@cache
def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render(source: str, **values: str) -> str:
    environment = Environment(
        undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True
    )
    return environment.from_string(source).render(**values).strip()
