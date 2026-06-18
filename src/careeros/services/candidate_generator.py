from __future__ import annotations

import re
from dataclasses import dataclass

from careeros.db.models.fact_staging import CandidateKind


SECTION_HEADINGS: dict[str, str] = {
    "education": "education",
    "academic background": "education",
    "projects": "projects",
    "project": "projects",
    "skills": "skills",
    "technical skills": "skills",
}

SKILL_SPLIT_PATTERN = re.compile(r"[,|/]| and ")
CLAIM_VERB_PATTERN = re.compile(
    r"\b(built|developed|created|designed|implemented|improved|deployed|trained|analyzed|led|optimized|engineered|made)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class LineRecord:
    text: str
    start: int
    end: int


@dataclass(slots=True)
class CandidateSeed:
    candidate_kind: CandidateKind
    structured_data: dict[str, object]
    evidence_spans: list[LineRecord]
    parent_key: str | None = None


def generate_candidates(extracted_text: str) -> list[CandidateSeed]:
    line_records = _build_line_records(extracted_text)
    sections = _partition_sections(line_records)

    candidates: list[CandidateSeed] = []
    candidates.extend(_generate_education_candidates(sections.get("education", [])))
    candidates.extend(_generate_project_candidates(sections.get("projects", [])))
    candidates.extend(_generate_skill_candidates(sections.get("skills", [])))
    candidates.extend(_generate_claim_candidates(sections.get("projects", [])))
    return candidates


def _build_line_records(extracted_text: str) -> list[LineRecord]:
    records: list[LineRecord] = []
    cursor = 0
    for line in extracted_text.splitlines(keepends=True):
        raw_line = line.rstrip("\n")
        records.append(LineRecord(text=raw_line, start=cursor, end=cursor + len(raw_line)))
        cursor += len(line)
    return records


def _partition_sections(line_records: list[LineRecord]) -> dict[str, list[LineRecord]]:
    sections: dict[str, list[LineRecord]] = {}
    current_section: str | None = None

    for record in line_records:
        normalized = _normalize_heading(record.text)
        if normalized in SECTION_HEADINGS:
            current_section = SECTION_HEADINGS[normalized]
            sections.setdefault(current_section, [])
            continue
        if current_section is None:
            continue
        sections[current_section].append(record)
    return sections


def _normalize_heading(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z ]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


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


def _generate_project_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    for index, block in enumerate(_group_blocks(records)):
        header = block[0].text.strip(" -\t")
        details = [line.text.strip(" -\t") for line in block[1:] if line.text.strip()]
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
        _, _, tail = line.partition(":")
        skill_text = tail if tail else line
        for raw_token in SKILL_SPLIT_PATTERN.split(skill_text):
            skill = raw_token.strip(" -\t•")
            if len(skill) < 2:
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
    return candidates


def _generate_claim_candidates(records: list[LineRecord]) -> list[CandidateSeed]:
    candidates: list[CandidateSeed] = []
    current_project_index = -1
    for record in records:
        stripped = record.text.strip()
        if not stripped:
            continue

        if not stripped.startswith(("-", "*", "•")):
            current_project_index += 1
            continue

        claim_text = stripped.lstrip("-*• ").strip()
        if not claim_text:
            continue
        if not CLAIM_VERB_PATTERN.search(claim_text) and not re.search(r"\d", claim_text):
            continue

        candidates.append(
            CandidateSeed(
                candidate_kind=CandidateKind.CLAIM,
                structured_data={
                    "claim_text": claim_text,
                    "source_section": "projects",
                },
                evidence_spans=[LineRecord(claim_text, record.start, record.end)],
                parent_key=f"project:{max(current_project_index, 0)}",
            )
        )
    return candidates
