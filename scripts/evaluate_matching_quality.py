#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.services.embedding_provider import (  # noqa: E402
    EmbeddingProviderUnavailableError,
    build_embedding_provider,
)


ML_PROFILE_CLAIMS = [
    "Built machine learning models using Python, PyTorch, pandas, NumPy, and SQL.",
    "Analyzed datasets, trained models, and evaluated results with clear reporting.",
    "Created AI and data science projects using notebooks and model experimentation.",
]

BACKEND_PROFILE_CLAIMS = [
    "Built backend APIs using Python, FastAPI, PostgreSQL, Docker, SQL, and Git.",
    "Implemented service endpoints, database models, tests, and deployment workflows.",
    "Designed reliable application backend logic for internship discovery systems.",
]

SKILL_ALIASES = {
    "python": "python",
    "pytorch": "pytorch",
    "machine learning": "machine learning",
    "deep learning": "deep learning",
    "pandas": "pandas",
    "numpy": "numpy",
    "sql": "sql",
    "fastapi": "fastapi",
    "postgresql": "postgresql",
    "docker": "docker",
    "git": "git",
    "javascript": "javascript",
    "react": "react",
    "css": "css",
}

ROLE_KEYWORDS = {
    "ml": {"machine learning", "ml", "ai", "deep learning"},
    "data": {"data", "analytics", "analysis", "statistics"},
    "backend": {"backend", "api", "fastapi", "postgresql", "service"},
    "frontend": {"frontend", "react", "javascript", "css", "ui"},
}


@dataclass(slots=True)
class ScoreRow:
    profile_name: str
    title: str
    total_score: float
    semantic_score: float
    skill_score: float
    role_score: float


def main() -> int:
    settings = Settings()
    provider = build_embedding_provider(settings)
    internships = _load_sample_internships()

    try:
        ml_rows = _score_profile("ML profile", ML_PROFILE_CLAIMS, internships, provider)
        backend_rows = _score_profile("Backend profile", BACKEND_PROFILE_CLAIMS, internships, provider)
    except EmbeddingProviderUnavailableError as exc:
        print(f"Embedding provider unavailable: {exc}", file=sys.stderr)
        return 1

    print("CareerOS matching quality evaluation")
    print(f"provider: {settings.embedding_provider}")
    print(f"model: {provider.model_name}")
    print(f"embedding_version: {provider.embedding_version}")
    print()
    _print_rows(ml_rows)
    print()
    _print_rows(backend_rows)
    print()

    checks = [
        (
            "ML profile ranks ML/Data internships above Frontend",
            _rank(ml_rows, "Machine Learning Intern") < _rank(ml_rows, "Frontend Intern")
            and _rank(ml_rows, "Data Science Intern") < _rank(ml_rows, "Frontend Intern"),
        ),
        (
            "Backend profile ranks Backend internship highest",
            _rank(backend_rows, "Backend Intern") == 0,
        ),
        (
            "Irrelevant Frontend internship scores lower for backend profile",
            _score(backend_rows, "Backend Intern") > _score(backend_rows, "Frontend Intern"),
        ),
    ]

    print("Checks")
    all_passed = True
    for label, passed in checks:
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"
        print(f"- {status}: {label}")
    return 0 if all_passed else 1


def _load_sample_internships() -> list[dict[str, str]]:
    path = ROOT_DIR / "samples" / "demo_internships.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _score_profile(
    profile_name: str,
    claims: list[str],
    internships: list[dict[str, str]],
    provider: object,
) -> list[ScoreRow]:
    profile_text = "\n".join(claims)
    profile_vector = provider.embed_text(profile_text)  # type: ignore[attr-defined]
    profile_skills = _extract_skills(profile_text)
    profile_roles = _extract_roles(profile_text)

    rows = []
    for internship in internships:
        internship_text = _internship_text(internship)
        internship_vector = provider.embed_text(internship_text)  # type: ignore[attr-defined]
        internship_skills = _extract_skills(internship_text)
        internship_roles = _extract_roles(internship_text)

        semantic_score = max(0.0, _cosine(profile_vector, internship_vector)) * 100.0
        skill_score = _overlap_score(profile_skills, internship_skills)
        role_score = _overlap_score(profile_roles, internship_roles)
        total_score = 0.55 * semantic_score + 0.35 * skill_score + 0.10 * role_score
        rows.append(
            ScoreRow(
                profile_name=profile_name,
                title=internship["title"],
                total_score=total_score,
                semantic_score=semantic_score,
                skill_score=skill_score,
                role_score=role_score,
            )
        )

    rows.sort(key=lambda row: row.total_score, reverse=True)
    return rows


def _internship_text(internship: dict[str, str]) -> str:
    return "\n".join(
        value
        for value in (
            internship.get("title", ""),
            internship.get("description", ""),
            internship.get("requirements", ""),
            internship.get("responsibilities", ""),
        )
        if value
    )


def _extract_skills(text: str) -> set[str]:
    normalized = text.casefold()
    return {
        canonical
        for alias, canonical in SKILL_ALIASES.items()
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
    }


def _extract_roles(text: str) -> set[str]:
    normalized = text.casefold()
    return {
        role
        for role, keywords in ROLE_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return (len(left & right) / len(right)) * 100.0


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _print_rows(rows: list[ScoreRow]) -> None:
    if not rows:
        return
    print(rows[0].profile_name)
    print("rank | internship                 | total | semantic | skill | role")
    print("-----+----------------------------+-------+----------+-------+------")
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>4} | {row.title:<26} | "
            f"{row.total_score:>5.1f} | {row.semantic_score:>8.1f} | "
            f"{row.skill_score:>5.1f} | {row.role_score:>4.1f}"
        )


def _rank(rows: list[ScoreRow], title: str) -> int:
    for index, row in enumerate(rows):
        if row.title == title:
            return index
    raise ValueError(f"Internship not found in evaluation rows: {title}")


def _score(rows: list[ScoreRow], title: str) -> float:
    for row in rows:
        if row.title == title:
            return row.total_score
    raise ValueError(f"Internship not found in evaluation rows: {title}")


if __name__ == "__main__":
    raise SystemExit(main())
