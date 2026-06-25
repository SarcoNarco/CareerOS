from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import SkillAlias, SkillCatalog


def list_skills(session: Session) -> list[SkillCatalog]:
    return list(
        session.scalars(
            select(SkillCatalog)
            .options(selectinload(SkillCatalog.aliases))
            .order_by(SkillCatalog.category.asc(), SkillCatalog.name.asc())
        )
    )


def normalize_skill(session: Session, raw_skill_name: str) -> SkillCatalog | None:
    alias = raw_skill_name.casefold().strip()
    if not alias:
        return None

    skill_alias = session.scalar(
        select(SkillAlias)
        .options(selectinload(SkillAlias.skill))
        .where(SkillAlias.alias == alias)
    )
    if skill_alias is not None:
        return skill_alias.skill

    return session.scalar(select(SkillCatalog).where(SkillCatalog.name == raw_skill_name.strip()))
