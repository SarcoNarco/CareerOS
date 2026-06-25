from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.models.internship import (
    NormalizedLocation,
    NormalizedTitle,
    SkillAlias,
    SkillCatalog,
    TitleAlias,
    WorkMode,
)


INITIAL_SKILLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Python", "programming_language", ("python", "py")),
    ("SQL", "database", ("sql",)),
    ("PostgreSQL", "database", ("postgresql", "postgres", "psql")),
    ("Machine Learning", "ai_ml", ("machine learning", "ml")),
    ("Deep Learning", "ai_ml", ("deep learning", "dl")),
    ("PyTorch", "ai_ml", ("pytorch", "torch")),
    ("TensorFlow", "ai_ml", ("tensorflow", "tf")),
    ("scikit-learn", "ai_ml", ("scikit-learn", "sklearn", "scikit learn")),
    ("Pandas", "data", ("pandas",)),
    ("NumPy", "data", ("numpy", "np")),
    ("FastAPI", "backend", ("fastapi",)),
    ("Docker", "devops", ("docker", "containerization")),
    ("Git", "tooling", ("git", "github")),
    ("JavaScript", "programming_language", ("javascript", "js")),
    ("TypeScript", "programming_language", ("typescript", "ts")),
    ("React", "frontend", ("react", "react.js", "reactjs")),
    ("CSS", "frontend", ("css", "css3")),
    ("HTML", "frontend", ("html", "html5")),
    ("Node.js", "backend", ("node.js", "nodejs", "node")),
    ("REST APIs", "backend", ("rest", "rest api", "rest apis", "api development")),
    ("AWS", "cloud", ("aws", "amazon web services")),
    ("Kubernetes", "devops", ("kubernetes", "k8s")),
    ("Linux", "tooling", ("linux",)),
    ("Java", "programming_language", ("java",)),
    ("Go", "programming_language", ("go", "golang")),
    ("C++", "programming_language", ("c++", "cpp")),
)

INITIAL_TITLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "ML",
        "ml",
        ("machine learning intern", "ml intern", "ai intern", "ml engineer intern", "machine learning internship"),
    ),
    (
        "Data",
        "data",
        ("data analyst intern", "data science intern", "data intern", "data scientist intern"),
    ),
    (
        "SWE",
        "swe",
        ("software engineer intern", "software engineering intern", "backend intern", "software developer intern", "sde intern"),
    ),
    ("Other", "other", ("intern",)),
)

INITIAL_LOCATIONS: tuple[tuple[str, WorkMode], ...] = (
    ("Remote", WorkMode.REMOTE),
    ("Hybrid", WorkMode.HYBRID),
    ("Onsite", WorkMode.ONSITE),
    ("Unknown", WorkMode.UNKNOWN),
)


def ensure_normalization_seed_data(session: Session) -> None:
    for name, category, aliases in INITIAL_SKILLS:
        skill = session.scalar(select(SkillCatalog).where(SkillCatalog.name == name))
        if skill is None:
            skill = SkillCatalog(name=name, category=category)
            session.add(skill)
            session.flush()
        _ensure_skill_aliases(session=session, skill=skill, aliases=aliases)

    for canonical_title, role_family, aliases in INITIAL_TITLES:
        title = session.scalar(
            select(NormalizedTitle).where(NormalizedTitle.canonical_title == canonical_title)
        )
        if title is None:
            title = NormalizedTitle(canonical_title=canonical_title, role_family=role_family)
            session.add(title)
            session.flush()
        _ensure_title_aliases(session=session, title=title, aliases=aliases)

    for canonical_label, work_mode in INITIAL_LOCATIONS:
        location = session.scalar(
            select(NormalizedLocation).where(NormalizedLocation.canonical_label == canonical_label)
        )
        if location is None:
            session.add(
                NormalizedLocation(
                    canonical_label=canonical_label,
                    country=None,
                    city=None,
                    region=None,
                    work_mode=work_mode,
                )
            )

    session.commit()


def _ensure_skill_aliases(
    session: Session,
    skill: SkillCatalog,
    aliases: Iterable[str],
) -> None:
    for alias in aliases:
        normalized_alias = alias.casefold().strip()
        existing = session.scalar(select(SkillAlias).where(SkillAlias.alias == normalized_alias))
        if existing is None:
            session.add(
                SkillAlias(
                    skill_id=skill.id,
                    alias=normalized_alias,
                    normalization_source="manual",
                )
            )


def _ensure_title_aliases(
    session: Session,
    title: NormalizedTitle,
    aliases: Iterable[str],
) -> None:
    for alias in aliases:
        normalized_alias = alias.casefold().strip()
        existing = session.scalar(select(TitleAlias).where(TitleAlias.alias == normalized_alias))
        if existing is None:
            session.add(
                TitleAlias(
                    normalized_title_id=title.id,
                    alias=normalized_alias,
                )
            )
