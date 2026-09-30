"""On-disk embedding cache. A hit does not call the embedding model again."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    model_id: str
    calls: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return one vector per text, shape ``(len(texts), dim)``."""


class HashEmbedder:
    """Deterministic local stand-in. No network and no model download."""

    def __init__(self, model_id: str, *, dimension: int = 16) -> None:
        self.model_id = model_id
        self.dimension = dimension
        self.calls = 0

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        return np.stack([_vector(self.model_id, text, self.dimension) for text in texts])


def cached_embed(
    embedder: Embedder,
    template: str,
    corpus_hash: str,
    texts: list[str],
    cache_dir: Path,
) -> np.ndarray:
    """Load vectors for ``(model, template, corpus hash)`` or compute and store them."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = f"{embedder.model_id}|{template}|{corpus_hash}".encode()
    path = cache_dir / f"{hashlib.sha256(key).hexdigest()}.npy"
    if path.is_file():
        return np.asarray(np.load(path))
    vectors = embedder.embed(texts)
    np.save(path, vectors)
    return vectors


def _vector(model_id: str, text: str, dimension: int) -> np.ndarray:
    digest = hashlib.sha256(f"{model_id}\0{text}".encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    return rng.normal(size=dimension)
