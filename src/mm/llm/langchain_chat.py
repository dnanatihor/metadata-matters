"""Chat models via LangChain ``init_chat_model``. Imported only for a live run."""

from __future__ import annotations

from typing import Protocol, cast

from mm.data.bird import Example
from mm.llm.budget import ASSUMED_OUTPUT_TOKENS, estimate_input_tokens
from mm.llm.runner import RateLimitError
from mm.llm.stub import Completion


class _Invokable(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> object:
        """Return a LangChain message."""


class LangChainChat:
    """One configured chat model. Temperature is 0."""

    def __init__(self, model_id: str, provider: str, *, chat: _Invokable | None = None) -> None:
        self.model_id = model_id
        self.provider = provider
        self._chat = chat

    def complete(self, full_prompt: str, *, example: Example) -> Completion:
        del example
        try:
            message = self._model().invoke([{"role": "user", "content": full_prompt}])
        except Exception as exc:
            if _is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc
            raise
        text = _message_text(message)
        input_tokens, output_tokens = _token_counts(message, full_prompt, text)
        return Completion(text=text, input_tokens=input_tokens, output_tokens=output_tokens)

    def _model(self) -> _Invokable:
        if self._chat is not None:
            return self._chat
        from langchain.chat_models import init_chat_model

        created = init_chat_model(self.model_id, model_provider=self.provider, temperature=0)
        if not hasattr(created, "invoke"):
            message = f"{self.model_id} did not produce a chat model"
            raise TypeError(message)
        chat = cast(_Invokable, created)
        self._chat = chat
        return chat


def _is_rate_limit(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if type(current).__name__ == "RateLimitError":
            return True
        if getattr(current, "status_code", None) == 429:
            return True
        current = current.__cause__
    return False


def _message_text(message: object) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def _token_counts(message: object, full_prompt: str, text: str) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        raw_input = usage.get("input_tokens")
        raw_output = usage.get("output_tokens")
        if isinstance(raw_input, int) and isinstance(raw_output, int):
            return raw_input, raw_output
    return estimate_input_tokens(full_prompt), max(ASSUMED_OUTPUT_TOKENS, len(text))
