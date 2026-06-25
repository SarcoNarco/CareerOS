#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.services.embedding_provider import (  # noqa: E402
    EmbeddingProviderUnavailableError,
    build_embedding_provider,
)


SAMPLE_TEXTS = [
    "Built machine learning models using Python, PyTorch, pandas, NumPy, and SQL.",
    "Developed deep learning experiments and evaluated model performance.",
    "Implemented backend APIs using FastAPI, PostgreSQL, Docker, and Git.",
    "Designed responsive frontend components with React, JavaScript, CSS, and accessibility.",
]


def main() -> int:
    settings = Settings()
    provider = build_embedding_provider(settings)

    try:
        vectors = [provider.embed_text(text) for text in SAMPLE_TEXTS]
    except EmbeddingProviderUnavailableError as exc:
        print(f"Embedding provider unavailable: {exc}", file=sys.stderr)
        return 1

    dimension = len(vectors[0]) if vectors else 0
    print("CareerOS embedding smoke check")
    print(f"provider: {settings.embedding_provider}")
    print(f"model: {provider.model_name}")
    print(f"embedding_version: {provider.embedding_version}")
    print(f"configured_dimension: {settings.embedding_dimension}")
    print(f"actual_dimension: {dimension}")
    print()
    print("Similarity examples")
    print(f"ML claim vs ML internship: {_cosine(vectors[0], vectors[1]):.4f}")
    print(f"ML claim vs Backend internship: {_cosine(vectors[0], vectors[2]):.4f}")
    print(f"ML claim vs Frontend internship: {_cosine(vectors[0], vectors[3]):.4f}")
    return 0


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


if __name__ == "__main__":
    raise SystemExit(main())
