from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from careeros.db.models.fact_staging import CandidateKind


SECTION_HEADINGS: dict[str, str] = {
    "education": "education",
    "academics": "education",
    "academic background": "education",
    "academic qualifications": "education",
    "qualifications": "education",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "internship experience": "experience",
    "employment": "experience",
    "positions of responsibility": "experience",
    "projects": "projects",
    "project": "projects",
    "academic projects": "projects",
    "personal projects": "projects",
    "technical projects": "projects",
    "selected projects": "projects",
    "relevant projects": "projects",
    "skills": "skills",
    "technical skills": "skills",
    "technical skill": "skills",
    "technologies": "skills",
    "tools": "skills",
    "certifications": "certifications",
    "certification": "certifications",
    "achievements": "achievements",
    "awards": "achievements",
    "links": "links",
    "profiles": "links",
}

MAX_SKILL_CANDIDATES = 28
MAX_SKILL_TOKEN_LENGTH = 48
SKILL_SPLIT_PATTERN = re.compile(r"[,|/;•]|\s+and\s+")
CLAIM_VERB_PATTERN = re.compile(
    r"\b("
    r"built|developed|created|designed|implemented|improved|deployed|trained|"
    r"analyzed|analysed|led|optimized|optimised|engineered|made|integrated|"
    r"automated|architected|launched|delivered|reduced|increased|ranked|"
    r"achieved|managed|collaborated|visualized|processed|predicted|classified"
    r")\b",
    re.IGNORECASE,
)
BULLET_PATTERN = re.compile(r"^\s*(?:[-*•●▪◦‣]|\d+[.)])\s+")
DATE_PATTERN = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\b|\b20\d{2}\b",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://|github\.com|linkedin\.com", re.IGNORECASE)
SKILL_CATEGORY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z &/+.-]{1,32}:\s*")
NOISE_SKILL_TOKENS = {
    "skills",
    "technical skills",
    "languages",
    "frameworks",
    "tools",
    "technologies",
}


@dataclass(slots=True)
class LineRecord:
    text: str
    start: int
    end: int


@dataclass(slots=True)
class SectionRecord:
    name: str
    heading: str
    heading_start: int
    heading_end: int
    lines: list[LineRecord] = field(default_factory=list)


@dataclass(slots=True)
class CandidateSeed:
    candidate_kind: CandidateKind
    structured_data: dict[str, object]
    evidence_spans: list[LineRecord]
    parent_key: str | None = None


@dataclass(slots=True)
class CandidateGenerationResult:
    candidates: list[CandidateSeed]
    diagnostics: dict[str, object]


def generate_candidates(extracted_text: str) -> list[CandidateSeed]:
    return generate_candidates_with_diagnostics(extracted_text).candidates


def generate_candidates_with_diagnostics(extracted_text: str) -> CandidateGenerationResult:
    line_records = _build_line_records(extracted_text)
    sections = _partition_sections(line_records)

    candidates: list[CandidateSeed] = []
    candidates.extend(_generate_education_candidates(_section_lines(sections, "education")))
    candidates.extend(_generate_experience_candidates(_section_lines(sections, "experience")))
    candidates.extend(_generate_project_candidates(_section_lines(sections, "projects")))
    candidates.extend(_generate_skill_candidates(_section_lines(sections, "skills")))
    candidates.extend(
        _generate_claim_candidates(
            _section_lines(sections, "projects"),
            source_section="projects",
            parent_prefix="project",
        )
    )
    candidates.extend(
        _generate_claim_candidates(
            _section_lines(sections, "experience"),
            source_section="experience",
            parent_prefix="experience",
        )
    )
    diagnostics = _build_diagnostics(
        extracted_text=extracted_text,
        sections=sections,
        candidates=candidates,
    )
    return CandidateGenerationResult(candidates=candidates, diagnostics=diagnostics)


def _build_line_records(extracted_text: str) -> list[LineRecord]:
    records: list[LineRecord] = []
    cursor = 0
    for line in extracted_text.splitlines(keepends=True):
        raw_line = line.rstrip("\n")
        records.append(LineRecord(text=raw_line, start=cursor, end=cursor + len(raw_line)))
        cursor += len(line)
    return records


def _partition_sections(line_records: list[LineRecord]) -> dict[str, SectionRecord]:
    sections: dict[str, SectionRecord] = {}
    current_section: SectionRecord | None = None

    for record in line_records:
        normalized = _normalize_heading(record.text)
        section_name = SECTION_HEADINGS.get(normalized)
        if section_name is not None:
            current_section = SectionRecord(
                name=section_name,
                heading=record.text.strip(),
                heading_start=record.start,
                heading_end=record.end,
            )
            sections[section_name] = current_section
            continue
        if current_section is None:
            continue
        current_section.lines.append(record)
    return sections


def _normalize_heading(value: str) -> str:
    stripped = value.strip()
    if len(stripped) > 48:
        return ""
    stripped = stripped.strip(":|/-—–")
    cleaned = re.sub(r"[^a-zA-Z &/+]+", " ", stripped).strip().lower()
    cleaned = cleaned.replace("&", " and ")
    return re.sub(r"\s+", " ", cleaned)


def _section_lines(sections: dict[str, SectionRecord], name: str) -> list[LineRecord]:
    section = sections.get(name)
    return section.lines if section else []


def _group_blocks(records: list[LineRecord]) -> list[list[LineRecord]]:
    blocks: list[list[LineRecord]] = []
    current: list[LineRecord] = []
    for record in records:
        if not record.text.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(record)
    if current:
        blocks.append(current)
    return blocks


def _group_entity_blocks(records: list[LineRecord]) -> list[list[LineRecord]]:
    blocks: list[list[LineRecord]] = []
    current: list[LineRecord] = []
    for record in records:
        stripped = record.text.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue

        if _is_entity_header(record) and current:
            blocks.append(current)
            current = [record]
            continue
        current.append(record)

    if current:
        blocks.append(current)
    return blocks


def _is_entity_header(record: LineRecord) -> bool:
    text = record.text.strip()
    if not text or _is_bullet(text):
        return False
    if URL_PATTERN.search(text):
        return False
    if len(text) > 120:
        return False
    if CLAIM_VERB_PATTERN.search(text):
        return False
    if text.endswith("."):
        return False
    return True


def _generate_education_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    for block in _group_blocks(records):
        joined = " ".join(line.text.strip(" -\t") for line in block if line.text.strip())
        if not joined:
            continue
        parts = [part.strip() for part in re.split(r"[-|,]", joined) if part.strip()]
        institution_name = parts[0] if parts else joined
        candidates.append(
            CandidateSeed(
                candidate_kind=CandidateKind.EDUCATION,
                structured_data={
                    "institution_name": institution_name,
                    "raw_text": joined,
                },
                evidence_spans=[LineRecord(joined, block[0].start, block[-1].end)],
            )
        )
    return candidates


def _generate_experience_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    for index, block in enumerate(_group_entity_blocks(records)):
        meaningful = [line for line in block if line.text.strip()]
        if not meaningful:
            continue
        header = meaningful[0].text.strip(" -\t")
        details = [_clean_bullet_text(line.text) for line in meaningful[1:] if line.text.strip()]
        summary = " ".join(details) if details else header
        candidates.append(
            CandidateSeed(
                candidate_kind=CandidateKind.EXPERIENCE,
                structured_data={
                    "role_or_company": header,
                    "summary": summary,
                    "raw_text": " ".join(line.text.strip() for line in meaningful),
                },
                evidence_spans=[LineRecord(" ".join(line.text.strip() for line in meaningful), meaningful[0].start, meaningful[-1].end)],
                parent_key=f"experience:{index}",
            )
        )
    return candidates


def _generate_project_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    for index, block in enumerate(_group_entity_blocks(records)):
        header = block[0].text.strip(" -\t")
        details = [_clean_bullet_text(line.text) for line in block[1:] if line.text.strip()]
        summary = " ".join(details) if details else header
        candidates.append(
            CandidateSeed(
                candidate_kind=CandidateKind.PROJECT,
                structured_data={
                    "name": header,
                    "summary": summary,
                    "raw_text": " ".join(line.text.strip() for line in block),
                },
                evidence_spans=[LineRecord(summary, block[0].start, block[-1].end)],
                parent_key=f"project:{index}",
            )
        )
    return candidates


def _generate_skill_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    seen: set[str] = set()
    for record in records:
        line = record.text.strip()
        if not line:
            continue
        if len(line) > 220 and ":" not in line:
            continue
        skill_text = SKILL_CATEGORY_PATTERN.sub("", line)
        for raw_token in SKILL_SPLIT_PATTERN.split(skill_text):
            skill = _clean_skill_token(raw_token)
            if not skill:
                continue
            normalized = skill.lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            token_start = record.text.lower().find(skill.lower())
            start = record.start + max(token_start, 0)
            end = start + len(skill)
            candidates.append(
                CandidateSeed(
                    candidate_kind=CandidateKind.SKILL,
                    structured_data={"skill_name": skill},
                    evidence_spans=[LineRecord(skill, start, end)],
                )
            )
            if len(candidates) >= MAX_SKILL_CANDIDATES:
                return candidates
    return candidates


def _generate_claim_candidates(
    records: list[LineRecord],
    *,
    source_section: str,
    parent_prefix: str,
) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    current_project_index = -1
    for record in records:
        stripped = record.text.strip()
        if not stripped:
            continue

        if not _is_bullet(stripped):
            current_project_index += 1
            continue

        claim_text = _clean_bullet_text(stripped)
        if not claim_text:
            continue
        if not _looks_like_claim(claim_text):
            continue

        candidates.append(
            CandidateSeed(
                candidate_kind=CandidateKind.CLAIM,
                structured_data={
                    "claim_text": claim_text,
                    "source_section": source_section,
                    "claim_type": source_section.rstrip("s"),
                },
                evidence_spans=[LineRecord(claim_text, record.start, record.end)],
                parent_key=f"{parent_prefix}:{max(current_project_index, 0)}",
            )
        )
    return candidates


def _is_bullet(value: str) -> bool:
    return bool(BULLET_PATTERN.match(value))


def _clean_bullet_text(value: str) -> str:
    return BULLET_PATTERN.sub("", value.strip()).strip(" \t-•*")


def _clean_skill_token(value: str) -> str | None:
    token = value.strip(" \t-•*()[]{}")
    token = re.sub(r"\s+", " ", token)
    token = re.sub(r"\b(?:and|or)$", "", token, flags=re.IGNORECASE).strip()
    if len(token) < 2 or len(token) > MAX_SKILL_TOKEN_LENGTH:
        return None
    normalized = token.lower()
    if normalized in NOISE_SKILL_TOKENS:
        return None
    if DATE_PATTERN.search(token) or URL_PATTERN.search(token):
        return None
    if token.count(" ") > 4:
        return None
    return token


def _looks_like_claim(value: str) -> bool:
    if CLAIM_VERB_PATTERN.search(value):
        return True
    if re.search(r"\d", value) and len(value.split()) >= 4:
        return True
    return False


def _build_diagnostics(
    *,
    extracted_text: str,
    sections: dict[str, SectionRecord],
    candidates: list[CandidateSeed],
) -> dict[str, object]:
    candidate_counts = Counter(seed.candidate_kind.value for seed in candidates)
    claim_counts = Counter(
        str(seed.structured_data.get("source_section", "unknown"))
        for seed in candidates
        if seed.candidate_kind == CandidateKind.CLAIM
    )
    section_report = {
        name: {
            "heading": section.heading,
            "line_count": len([line for line in section.lines if line.text.strip()]),
            "start": section.heading_start,
            "end": section.lines[-1].end if section.lines else section.heading_end,
        }
        for name, section in sections.items()
    }
    warnings = _build_warnings(
        extracted_text=extracted_text,
        sections=sections,
        candidate_counts=candidate_counts,
    )
    return {
        "sections_detected": section_report,
        "candidate_counts_by_type": dict(candidate_counts),
        "claim_counts_by_type": dict(claim_counts),
        "warnings": warnings,
        "quality_metrics": {
            "detected_section_count": len(sections),
            "candidate_count": len(candidates),
            "claim_candidate_count": candidate_counts.get(CandidateKind.CLAIM.value, 0),
            "skill_candidate_count": candidate_counts.get(CandidateKind.SKILL.value, 0),
            "project_candidate_count": candidate_counts.get(CandidateKind.PROJECT.value, 0),
            "experience_candidate_count": candidate_counts.get(CandidateKind.EXPERIENCE.value, 0),
            "education_candidate_count": candidate_counts.get(CandidateKind.EDUCATION.value, 0),
            "text_length": len(extracted_text),
        },
    }


def _build_warnings(
    *,
    extracted_text: str,
    sections: dict[str, SectionRecord],
    candidate_counts: Counter[str],
) -> list[str]:
    warnings: list[str] = []
    if len(extracted_text.strip()) < 200:
        warnings.append("Extracted text is short; source document parsing may be incomplete.")
    for required_section in ("education", "projects", "skills"):
        if required_section not in sections:
            warnings.append(f"No {required_section} section detected.")
    if "experience" not in sections:
        warnings.append("No experience section detected.")
    if candidate_counts.get("project", 0) == 0:
        warnings.append("No project candidates generated.")
    if candidate_counts.get("claim", 0) == 0:
        warnings.append("No project or experience claim candidates generated.")
    if candidate_counts.get("skill", 0) > max(10, len([c for c in candidate_counts.elements() if c != "skill"]) * 4):
        warnings.append("Skill candidates dominate extraction; review section detection and skill parsing.")
    return warnings
