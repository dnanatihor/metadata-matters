"""Local sentence-transformers embedder. The library is imported on first use."""

from __future__ import annotations

from typing import Protocol, cast

import numpy as np


class _Encoder(Protocol):
    def encode(self, texts: list[str], *, normalize_embeddings: bool = False) -> object:
        """Return one vector per text."""


class SentenceTransformerEmbedder:
    """Local embedding model named by ``configs/models.yaml``."""

    def __init__(self, model_id: str, *, encoder: _Encoder | None = None) -> None:
        self.model_id = model_id
        self.calls = 0
        self._encoder = encoder

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        vectors = self._loaded().encode(texts, normalize_embeddings=False)
        return np.asarray(vectors, dtype=np.float64)

    def _loaded(self) -> _Encoder:
        if self._encoder is not None:
            return self._encoder
        from sentence_transformers import SentenceTransformer

        created = cast(_Encoder, SentenceTransformer(self.model_id))
        self._encoder = created
        return created
