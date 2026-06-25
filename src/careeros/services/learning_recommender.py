from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careeros.db.models.internship import InternshipSkillRequirement, SkillCatalog
from careeros.db.models.matching import InternshipMatch
from careeros.services.gap_analysis_service import analyze_match_gaps, collect_profile_skills


@dataclass(slots=True)
class SkillRecommendation:
    skill_id: UUID | None
    skill_name: str
    priority_score: Decimal
    demand_count: int
    matched_internship_count: int
    reason: str
    recommendation: str


def recommend_profile_skills(
    session: Session,
    profile_id: UUID,
    *,
    limit: int = 10,
) -> list[SkillRecommendation]:
    profile_skills = collect_profile_skills(session=session, profile_id=profile_id)
    matches = list(
        session.scalars(
            select(InternshipMatch)
            .where(InternshipMatch.profile_id == profile_id)
            .order_by(InternshipMatch.total_score.desc(), InternshipMatch.created_at.desc())
            .limit(50)
        )
    )

    scored: dict[tuple[UUID | None, str], dict[str, object]] = {}
    for match in matches:
        analysis = analyze_match_gaps(session=session, match_id=match.id)
        for gap in analysis.missing_skills:
            key = gap.skill_id, gap.skill_name_raw.casefold()
            entry = scored.setdefault(
                key,
                {
                    "skill_id": gap.skill_id,
                    "skill_name": gap.skill.name if gap.skill is not None else gap.skill_name_raw,
                    "matched_internship_count": 0,
                    "severity_total": 0,
                    "score_total": Decimal("0.00"),
                },
            )
            entry["matched_internship_count"] = int(entry["matched_internship_count"]) + 1
            entry["severity_total"] = int(entry["severity_total"]) + gap.severity
            entry["score_total"] = Decimal(entry["score_total"]) + Decimal(match.total_score)

    recommendations: list[SkillRecommendation] = []
    demand_counts = _market_demand_counts(session=session)
    for entry in scored.values():
        skill_id = entry["skill_id"]
        skill_name = str(entry["skill_name"])
        if skill_id is not None and skill_id in profile_skills.skill_ids:
            continue
        if skill_name.casefold() in profile_skills.normalized_names:
            continue

        matched_count = int(entry["matched_internship_count"])
        severity_total = int(entry["severity_total"])
        score_total = Decimal(entry["score_total"])
        demand_count = demand_counts.get((skill_id, skill_name.casefold()), 0)
        priority = (
            Decimal(matched_count * 3)
            + Decimal(severity_total)
            + (score_total / Decimal("25.0"))
            + Decimal(demand_count)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        recommendations.append(
            SkillRecommendation(
                skill_id=skill_id,
                skill_name=skill_name,
                priority_score=priority,
                demand_count=demand_count,
                matched_internship_count=matched_count,
                reason=(
                    f"{skill_name} is missing from approved claims and appears in "
                    f"{matched_count} matched internship(s). Market demand count: {demand_count}."
                ),
                recommendation=(
                    f"Create a small verified project, lab, or coursework artifact using {skill_name}."
                ),
            )
        )

    return sorted(
        recommendations,
        key=lambda item: (item.priority_score, item.demand_count, item.skill_name.casefold()),
        reverse=True,
    )[:limit]


def _market_demand_counts(session: Session) -> dict[tuple[UUID | None, str], int]:
    rows = session.execute(
        select(
            InternshipSkillRequirement.skill_id,
            SkillCatalog.name,
            InternshipSkillRequirement.skill_name_raw,
            func.count(func.distinct(InternshipSkillRequirement.internship_id)),
        )
        .outerjoin(SkillCatalog, SkillCatalog.id == InternshipSkillRequirement.skill_id)
        .group_by(
            InternshipSkillRequirement.skill_id,
            SkillCatalog.name,
            InternshipSkillRequirement.skill_name_raw,
        )
    )
    return {
        (row[0], (row[1] or row[2]).casefold()): int(row[3])
        for row in rows
    }
