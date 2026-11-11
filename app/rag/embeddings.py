"""Embedding providers.

Default is the free, local, Vietnamese-tuned model: AITeamVN/Vietnamese_Embedding_v2
(1024 dims, fine-tuned from BGE-M3, Apache-2.0). It runs on CPU, needs no API key,
and costs nothing per question.

torch is deliberately not in requirements.txt; install requirements-embed.txt
wherever embeddings run. Without it, retrieval still works keyword-only, which is
enough to develop the rest of the pipeline.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbedderError(RuntimeError):
    """Embeddings could not be produced."""


class EmbedderUnavailable(EmbedderError):
    """The local stack (sentence-transformers/torch) is not installed."""


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalEmbedder:
    """sentence-transformers on CPU, normalised so cosine similarity is a dot product."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        dim: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.name = model_name or settings.embed_model
        self.dim = dim or settings.embed_dim
        self._device = device or settings.embed_device
        self._batch_size = batch_size or settings.embed_batch_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on install
                raise EmbedderUnavailable(
                    "sentence-transformers chưa được cài: pip install -r requirements-embed.txt "
                    "(hoặc chạy ask.py với --no-embed để chỉ tìm bằng từ khoá)"
                ) from exc

            logger.info("loading embedding model %s (device=%s)", self.name, self._device)
            model = SentenceTransformer(self.name, device=self._device)
            actual_dim = model.get_sentence_embedding_dimension()
            if actual_dim and actual_dim != self.dim:
                raise EmbedderError(
                    f"{self.name} xuất vector {actual_dim} chiều nhưng EMBED_DIM={self.dim}; "
                    "sửa EMBED_DIM rồi tạo lại cột chunks.embedding"
                )
            self._model = model
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(list(texts))

    def embed_query(self, text: str) -> list[float]:
        vectors = self._encode([text])
        if not vectors:
            raise EmbedderError("empty embedding result")
        return vectors[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in row] for row in vectors]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embed_provider == "none":
        raise EmbedderUnavailable("EMBED_PROVIDER=none: embeddings are disabled")
    return LocalEmbedder()
