from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    NormalizedTitle,
    SkillCatalog,
)


@dataclass(slots=True)
class MarketSkillAggregate:
    skill_id: UUID | None
    skill_name: str
    internship_count: int
    percentage: Decimal


@dataclass(slots=True)
class MarketTopSkills:
    role_family: str | None
    total_internships: int
    items: list[MarketSkillAggregate]


def get_top_market_skills(
    session: Session,
    *,
    role_family: str | None = None,
    limit: int = 20,
) -> MarketTopSkills:
    total_internships = _count_internships(session=session, role_family=role_family)
    if total_internships == 0:
        return MarketTopSkills(role_family=role_family, total_internships=0, items=[])

    statement = (
        select(
            InternshipSkillRequirement.skill_id,
            SkillCatalog.name,
            InternshipSkillRequirement.skill_name_raw,
            func.count(func.distinct(InternshipSkillRequirement.internship_id)).label(
                "internship_count"
            ),
        )
        .join(Internship, Internship.id == InternshipSkillRequirement.internship_id)
        .outerjoin(SkillCatalog, SkillCatalog.id == InternshipSkillRequirement.skill_id)
        .group_by(
            InternshipSkillRequirement.skill_id,
            SkillCatalog.name,
            InternshipSkillRequirement.skill_name_raw,
        )
        .order_by(
            func.count(func.distinct(InternshipSkillRequirement.internship_id)).desc(),
            func.coalesce(SkillCatalog.name, InternshipSkillRequirement.skill_name_raw).asc(),
        )
        .limit(limit)
    )
    if role_family is not None:
        statement = statement.join(
            NormalizedTitle,
            NormalizedTitle.id == Internship.normalized_title_id,
        ).where(func.lower(NormalizedTitle.role_family) == role_family.casefold())

    items = [
        MarketSkillAggregate(
            skill_id=row.skill_id,
            skill_name=row.name or row.skill_name_raw,
            internship_count=row.internship_count,
            percentage=_percentage(row.internship_count, total_internships),
        )
        for row in session.execute(statement)
    ]
    return MarketTopSkills(
        role_family=role_family,
        total_internships=total_internships,
        items=items,
    )


def _count_internships(session: Session, role_family: str | None) -> int:
    statement = select(func.count(func.distinct(Internship.id)))
    if role_family is not None:
        statement = (
            statement.join(NormalizedTitle, NormalizedTitle.id == Internship.normalized_title_id)
            .where(func.lower(NormalizedTitle.role_family) == role_family.casefold())
        )
    return int(session.scalar(statement) or 0)


def _percentage(count: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal("0.00")
    value = Decimal(count * 100) / Decimal(total)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
