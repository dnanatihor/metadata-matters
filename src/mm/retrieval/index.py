"""Brute-force cosine search over L2-normalised embeddings."""

from __future__ import annotations

import numpy as np

from mm.retrieval.corpus import Document


def rank_documents(
    query: np.ndarray, documents: tuple[Document, ...] | list[Document], vectors: np.ndarray
) -> list[Document]:
    """Return ``documents`` sorted by cosine similarity to ``query``, highest first."""
    if len(documents) != len(vectors):
        message = "documents and vectors must be the same length"
        raise ValueError(message)
    if len(documents) == 0:
        return []
    query_norm = _normalise(query.reshape(1, -1))
    matrix = _normalise(vectors)
    scores = (matrix @ query_norm.T).ravel()
    order = np.argsort(-scores, kind="stable")
    return [documents[int(index)] for index in order]


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe = np.maximum(norms, 1e-12)
    return np.asarray(vectors / safe)
