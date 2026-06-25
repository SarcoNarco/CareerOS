from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol

from careeros.core.config import Settings


class EmbeddingProviderUnavailableError(RuntimeError):
    """Raised when the configured local embedding provider cannot be initialized."""


class EmbeddingProvider(Protocol):
    model_name: str
    embedding_version: str
    dimension: int

    def embed_text(self, text: str) -> list[float]:
        ...


@dataclass(slots=True)
class DeterministicEmbeddingProvider:
    model_name: str
    embedding_version: str
    dimension: int

    def embed_text(self, text: str) -> list[float]:
        tokens = [token.strip().casefold() for token in text.split() if token.strip()]
        values = [0.0 for _ in range(self.dimension)]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[index] += sign
        return _normalize(values)


class SentenceTransformersEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.embedding_model_name
        self.embedding_version = settings.embedding_version
        self.dimension = settings.embedding_dimension
        self._model: object | None = None

    def embed_text(self, text: str) -> list[float]:
        model = self._load_model()
        embedding = model.encode(  # type: ignore[attr-defined]
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vector = [float(value) for value in embedding.tolist()]
        if len(vector) != self.dimension:
            self.dimension = len(vector)
        return vector

    def _load_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingProviderUnavailableError(
                    "EMBEDDING_PROVIDER=sentence-transformers requires the "
                    "`sentence-transformers` package. Install project dependencies or set "
                    "EMBEDDING_PROVIDER=deterministic for tests and demos."
                ) from exc
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise EmbeddingProviderUnavailableError(
                    "Unable to load local sentence-transformers model "
                    f"`{self.model_name}`. The first run may need to download the model "
                    "into the local Hugging Face cache; after that no remote embedding API "
                    "is required. Set EMBEDDING_PROVIDER=deterministic if you need an "
                    "offline smoke test."
                ) from exc
        return self._model


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "deterministic":
        return DeterministicEmbeddingProvider(
            model_name="deterministic-local",
            embedding_version=f"deterministic:{settings.embedding_dimension}:v1",
            dimension=settings.embedding_dimension,
        )
    return SentenceTransformersEmbeddingProvider(settings=settings)


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]
