from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from careeros.db.base import utc_now
from careeros.db.models.internship import Internship
from careeros.db.models.profile import Profile
from careeros.db.models.resume import (
    GeneratedResume,
    GeneratedResumeClaim,
    ResumeStatus,
    ResumeTemplate,
)
from careeros.db.models.verification import ApprovedClaim
from careeros.services.resume_claim_selector import SelectedClaim, select_resume_claims
from careeros.services.resume_renderer import (
    DEFAULT_TEMPLATE_NAME,
    DEFAULT_TEMPLATE_PATH,
    render_resume_html,
)


@dataclass(slots=True)
class AssembledSectionItem:
    claim: ApprovedClaim
    rendered_text: str


@dataclass(slots=True)
class AssembledSection:
    name: str
    items: list[AssembledSectionItem]


@dataclass(slots=True)
class GeneratedResumeResult:
    resume: GeneratedResume
    claim_links: list[GeneratedResumeClaim]


def generate_resume(
    *,
    session: Session,
    profile_id: UUID,
    internship_id: UUID | None,
    template_id: UUID | None,
    storage_root: Path,
    max_claims: int,
) -> GeneratedResumeResult:
    profile = _get_profile(session=session, profile_id=profile_id)
    internship = _get_internship(session=session, internship_id=internship_id)
    template = _get_or_create_template(session=session, template_id=template_id)
    selected_claims = select_resume_claims(
        session=session,
        profile_id=profile_id,
        internship_id=internship_id,
        max_claims=max_claims,
    )
    sections = _assemble_sections(selected_claims)
    if not any(section.items for section in sections):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No approved claims were selected for resume generation.",
        )

    timestamp = utc_now()
    resume = GeneratedResume(
        profile_id=profile.id,
        internship_id=internship.id if internship is not None else None,
        template_id=template.id,
        status=ResumeStatus.EXPORTED,
        rendered_html_path=None,
        rendered_pdf_path=None,
        created_at=timestamp,
    )
    session.add(resume)
    session.flush()

    context = _render_context(profile=profile, internship=internship, sections=sections)
    html = render_resume_html(context)
    html_path = _write_html_artifact(storage_root=storage_root, resume_id=resume.id, html=html)
    resume.rendered_html_path = str(html_path)

    claim_links: list[GeneratedResumeClaim] = []
    display_order = 0
    for section in sections:
        for item in section.items:
            link = GeneratedResumeClaim(
                generated_resume_id=resume.id,
                approved_claim_id=item.claim.id,
                section_name=section.name,
                display_order=display_order,
                rendered_text=item.rendered_text,
                created_at=timestamp,
            )
            session.add(link)
            claim_links.append(link)
            display_order += 1

    session.commit()
    return get_generated_resume(session=session, resume_id=resume.id)


def get_generated_resume(session: Session, resume_id: UUID) -> GeneratedResumeResult:
    resume = session.scalar(
        select(GeneratedResume)
        .options(
            joinedload(GeneratedResume.profile).joinedload(Profile.user),
            joinedload(GeneratedResume.internship),
            joinedload(GeneratedResume.template),
            selectinload(GeneratedResume.claim_links).selectinload(
                GeneratedResumeClaim.approved_claim
            ),
        )
        .where(GeneratedResume.id == resume_id)
    )
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    claim_links = sorted(resume.claim_links, key=lambda item: item.display_order)
    return GeneratedResumeResult(resume=resume, claim_links=claim_links)


def list_generated_resume_claims(
    *,
    session: Session,
    resume_id: UUID,
) -> list[GeneratedResumeClaim]:
    get_generated_resume(session=session, resume_id=resume_id)
    return list(
        session.scalars(
            select(GeneratedResumeClaim)
            .options(selectinload(GeneratedResumeClaim.approved_claim))
            .where(GeneratedResumeClaim.generated_resume_id == resume_id)
            .order_by(GeneratedResumeClaim.display_order.asc())
        )
    )


def list_generated_resumes(
    *,
    session: Session,
    profile_id: UUID,
) -> list[GeneratedResume]:
    _get_profile(session=session, profile_id=profile_id)
    return list(
        session.scalars(
            select(GeneratedResume)
            .options(
                joinedload(GeneratedResume.template),
                joinedload(GeneratedResume.internship),
            )
            .where(GeneratedResume.profile_id == profile_id)
            .order_by(GeneratedResume.created_at.desc(), GeneratedResume.id.asc())
        )
    )


def _get_profile(session: Session, profile_id: UUID) -> Profile:
    profile = session.scalar(
        select(Profile)
        .options(joinedload(Profile.user))
        .where(Profile.id == profile_id)
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


def _get_internship(session: Session, internship_id: UUID | None) -> Internship | None:
    if internship_id is None:
        return None
    internship = session.scalar(select(Internship).where(Internship.id == internship_id))
    if internship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")
    return internship


def _get_or_create_template(
    *,
    session: Session,
    template_id: UUID | None,
) -> ResumeTemplate:
    if template_id is not None:
        template = session.scalar(
            select(ResumeTemplate).where(
                ResumeTemplate.id == template_id,
                ResumeTemplate.is_active.is_(True),
            )
        )
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume template not found.",
            )
        return template

    template = session.scalar(
        select(ResumeTemplate).where(ResumeTemplate.name == DEFAULT_TEMPLATE_NAME)
    )
    if template is None:
        template = ResumeTemplate(
            name=DEFAULT_TEMPLATE_NAME,
            template_engine="jinja2",
            template_path=DEFAULT_TEMPLATE_PATH,
            is_active=True,
            created_at=utc_now(),
        )
        session.add(template)
        session.flush()
    return template


def _assemble_sections(selected_claims: list[SelectedClaim]) -> list[AssembledSection]:
    grouped: dict[str, list[AssembledSectionItem]] = {}
    for selected in selected_claims:
        section_name = _section_name(selected.claim)
        grouped.setdefault(section_name, []).append(
            AssembledSectionItem(
                claim=selected.claim,
                rendered_text=selected.claim.claim_text.strip(),
            )
        )
    order = ("Experience", "Projects", "Education", "Skills", "Highlights")
    return [
        AssembledSection(name=name, items=grouped[name])
        for name in order
        if name in grouped
    ]


def _section_name(claim: ApprovedClaim) -> str:
    owner = claim.owning_entity_type.casefold()
    claim_type = claim.claim_type.casefold()
    if owner == "experience":
        return "Experience"
    if owner == "project":
        return "Projects"
    if owner == "education":
        return "Education"
    if owner == "skill" or claim_type == "skill":
        return "Skills"
    return "Highlights"


def _render_context(
    *,
    profile: Profile,
    internship: Internship | None,
    sections: list[AssembledSection],
) -> dict[str, object]:
    target_label = None
    if internship is not None:
        target_label = f"{internship.title} at {internship.company_name}"
    return {
        "profile_name": profile.user.display_name,
        "headline": profile.headline,
        "target_label": target_label,
        "sections": [
            {
                "name": section.name,
                "claims": [
                    {
                        "approved_claim_id": str(item.claim.id),
                        "rendered_text": item.rendered_text,
                    }
                    for item in section.items
                ],
            }
            for section in sections
        ],
    }


def _write_html_artifact(*, storage_root: Path, resume_id: UUID, html: str) -> Path:
    output_dir = storage_root / "generated_resumes"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{resume_id}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path
