from __future__ import annotations

import builtins
import math

import pytest

from careeros.core.config import Settings
from careeros.services.embedding_provider import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderUnavailableError,
    SentenceTransformersEmbeddingProvider,
    build_embedding_provider,
)


def _settings(**overrides: object) -> Settings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "api_token": "test-token",
        "embedding_provider": "deterministic",
        "embedding_dimension": 16,
    }
    values.update(overrides)
    return Settings(**values)


def test_provider_selection_uses_deterministic_provider() -> None:
    provider = build_embedding_provider(_settings(embedding_provider="deterministic"))

    assert isinstance(provider, DeterministicEmbeddingProvider)
    assert provider.model_name == "deterministic-local"
    assert provider.embedding_version == "deterministic:16:v1"
    assert provider.dimension == 16


def test_provider_selection_accepts_sentence_transformers_name_without_eager_loading() -> None:
    settings = _settings(
        embedding_provider="sentence-transformers",
        embedding_dimension=384,
    )

    provider = build_embedding_provider(settings)

    assert isinstance(provider, SentenceTransformersEmbeddingProvider)
    assert provider.model_name == "BAAI/bge-small-en-v1.5"
    assert provider.embedding_version == "bge-small-en-v1.5:sentence-transformers:v1"
    assert provider.dimension == 384
    assert provider._model is None


def test_provider_selection_accepts_legacy_sentence_transformers_alias() -> None:
    settings = _settings(embedding_provider="sentence_transformers")

    assert settings.embedding_provider == "sentence-transformers"
    assert isinstance(build_embedding_provider(settings), SentenceTransformersEmbeddingProvider)


def test_deterministic_provider_is_stable_and_normalized() -> None:
    provider = DeterministicEmbeddingProvider(
        model_name="deterministic-local",
        embedding_version="deterministic:32:v1",
        dimension=32,
    )

    first = provider.embed_text("Python FastAPI PostgreSQL")
    second = provider.embed_text("Python FastAPI PostgreSQL")

    assert first == second
    assert len(first) == 32
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_sentence_transformers_provider_fails_clearly_when_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError("missing test dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    provider = SentenceTransformersEmbeddingProvider(
        _settings(embedding_provider="sentence-transformers")
    )

    with pytest.raises(EmbeddingProviderUnavailableError, match="sentence-transformers"):
        provider.embed_text("sample text")
