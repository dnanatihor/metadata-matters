"""Live chat and embedding adapters. No network and no provider SDK."""

from __future__ import annotations

import numpy as np
import pytest

from mm.data.bird import Example
from mm.llm.langchain_chat import LangChainChat
from mm.llm.runner import RateLimitError
from mm.retrieval.local_embed import SentenceTransformerEmbedder


class _Message:
    def __init__(self, content: str, usage: dict[str, int]) -> None:
        self.content = content
        self.usage_metadata = usage


class _Chat:
    def __init__(self, result: object) -> None:
        self.result = result

    def invoke(self, messages: list[dict[str, str]]) -> object:
        assert messages[0]["content"] == "prompt"
        return self.result


class _TooMany(Exception):
    status_code = 429


class _Limited:
    def invoke(self, messages: list[dict[str, str]]) -> object:
        raise _TooMany("slow down")


class _Encoder:
    def encode(self, texts: list[str], *, normalize_embeddings: bool = False) -> np.ndarray:
        assert normalize_embeddings is False
        return np.ones((len(texts), 2))


def test_langchain_chat_reads_text_and_usage() -> None:
    client = LangChainChat(
        "gpt-4.1-mini",
        "openai",
        chat=_Chat(_Message("```sql\nselect 1\n```", {"input_tokens": 11, "output_tokens": 4})),
    )
    example = Example(
        question_id=1, db_id="db", question="q", evidence="", sql="select 1", difficulty="simple"
    )
    completion = client.complete("prompt", example=example)
    assert completion.text.startswith("```sql")
    assert completion.input_tokens == 11
    assert completion.output_tokens == 4


def test_langchain_chat_maps_http_429_to_rate_limit() -> None:
    client = LangChainChat("gpt-4.1-mini", "openai", chat=_Limited())
    example = Example(
        question_id=1, db_id="db", question="q", evidence="", sql="select 1", difficulty="simple"
    )
    with pytest.raises(RateLimitError):
        client.complete("prompt", example=example)


def test_sentence_transformer_wrapper_uses_the_injected_encoder() -> None:
    embedder = SentenceTransformerEmbedder(
        "sentence-transformers/all-MiniLM-L6-v2", encoder=_Encoder()
    )
    vectors = embedder.embed(["a", "b"])
    assert vectors.shape == (2, 2)
    assert embedder.calls == 1
