# CareerOS Project Context

## Purpose

CareerOS is a personal AI-powered internship discovery and career optimization system.

It is initially designed for one primary user:

- A Computer Science student
- Seeking internships in Machine Learning, Artificial Intelligence, Data Science, and Software Engineering
- Targeting India and worldwide remote opportunities

CareerOS is not a SaaS product in its initial form. The first implementation should optimize for correctness, privacy, local ownership of data, and rapid iteration by a single developer-user.

## Core Product Thesis

The source of truth is a structured career profile, not a PDF resume.

Resumes are generated views of verified profile data. The system must never invent experience, skills, projects, impact, education details, or achievements that are not grounded in verified source information.

This means CareerOS is fundamentally a:

1. Personal knowledge system for career facts
2. Job ingestion and ranking engine
3. Gap analysis and recommendation engine
4. Resume generation system constrained by verified facts

## Primary Goals

CareerOS should:

1. Parse and understand a master resume and related source material
2. Convert career information into structured, queryable data
3. Collect internship postings from multiple trusted sources
4. Rank internships by relevance and fit
5. Explain why a job is a match
6. Identify missing skills and experience gaps
7. Generate tailored resumes only from verified profile facts
8. Support future expansion into a full career operating system

## Non-Goals For Initial Versions

The first implementation should avoid:

- Building a public multi-tenant SaaS platform
- Premature microservices
- Autonomous browser agents
- Complex multi-agent orchestration
- Fully automated application submission
- Overly broad career coaching features unrelated to internship search

## Product Principles

### 1. Structured Profile First

The canonical representation of the user is normalized structured data in PostgreSQL.

Resume PDFs are inputs and outputs, not the primary data model.

### 2. Verification Before Generation

Every profile fact used in tailored output should be traceable to a verified source:

- Resume
- Transcript
- Portfolio
- GitHub/project links
- Manual user entry

If a fact cannot be verified, it must not be used in generated resumes.

### 3. Local-First Where Practical

The system should prefer local inference, local storage, and local execution when it is practical and cost-effective. Remote models may be added behind a provider abstraction, but the architecture should not require them.

### 4. Modular Monolith First

The system should ship as a modular monolith:

- One codebase
- One primary API service
- One PostgreSQL database
- No mandatory worker process for the MVP
- Optional local model service

This keeps operations simple while preserving future extraction paths if scale or collaboration later justify them.

### 5. Human Review On Critical Boundaries

The system may automate extraction, scoring, and drafting, but should preserve human review for:

- Profile verification
- Resume template approval
- Final tailored resume generation
- New source onboarding when scraping logic is uncertain

### 6. Explainability Over Black-Box Ranking

Job ranking should be understandable. Score breakdowns and explanations must expose:

- Skill overlap
- Role alignment
- Experience alignment
- Location/work-mode alignment
- Gap signals

## Intended User Journey

1. Import master resume and supporting sources
2. Extract candidate facts into a structured profile
3. Review and verify extracted data
4. Ingest internship postings on a schedule
5. Deduplicate and normalize job postings
6. Rank postings against the structured profile
7. Inspect explanation and gap analysis
8. Generate a tailored resume from verified facts for selected opportunities

## MVP Definition

The MVP should support:

- One local user
- One verified structured profile
- Resume import and manual profile correction
- Internship ingestion from a small number of reliable sources
- Job deduplication and storage
- Embedding-assisted matching and explanation
- Skill gap detection
- Tailored resume generation from verified facts

The MVP does not need:

- Multi-user auth flows
- Advanced analytics dashboards
- Application tracking CRM depth
- Browser automation
- Full document editor UX

## Technical Constraints

- Python backend
- FastAPI
- PostgreSQL
- Docker
- Docker Compose
- Containerized architecture
- Embedding-based matching
- Modular design
- Future support for local LLMs
- Future support for multi-user mode

## Quality Priorities

From highest to lowest priority for early versions:

1. Truthfulness and factual grounding
2. Maintainability
3. Data privacy and local ownership
4. Explainable matching
5. Ease of extension
6. Performance
7. UI sophistication

## Canonical Read Order For Future Sessions

Future implementation sessions should reconstruct project context in this order:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/ARCHITECTURE_V2.md`
3. `docs/DECISIONS.md`
4. `docs/ROADMAP.md`

These four files are intended to be sufficient to recover project intent without relying on prior conversation history.

## Current Architectural Direction

The approved direction for current implementation is:

- Modular monolith
- PostgreSQL as system of record
- `pgvector` for embedding storage and similarity search
- FastAPI API layer
- No mandatory worker container in MVP
- Optional local model container for Ollama or equivalent
- Deterministic plus embedding-based hybrid ranking
- Verification-first resume generation pipeline

## Current Implementation Status

The repository currently implements these backend slices:

1. Profile creation
2. Resume upload and source document persistence
3. Local deterministic text extraction
4. Extraction runs
5. Fact candidates
6. Evidence spans
7. Human review endpoints for candidate approval, rejection, and edit-and-approve
8. Approved claims
9. Verification events
10. Manual internship source registry
11. Internship ingestion runs
12. Raw posting storage
13. Normalized internship storage with duplicate prevention

Important implementation details for future sessions:

- `source_documents.extracted_text` is populated locally during upload using deterministic extraction
- fact staging is persisted through `extraction_runs`, `fact_candidates`, and `fact_evidence_spans`
- claim approval is persisted through `approved_claims` and `verification_events`
- approved claims are now the only persisted text fragments intended for later matching and resume-generation workflows
- manual internship ingestion is implemented through `internship_sources`, `source_policies`, `ingestion_runs`, `raw_postings`, and `internships`
- the initial ingestion adapter accepts manual API payloads only; no external job board integrations exist yet
- internship normalization currently persists normalized title, normalized location, and work mode directly on `internships`
- duplicate internship creation is prevented using source-scoped dedupe keys and content hashes
- the system still does not implement embeddings, matching, skill gap analysis, or resume generation

## Key Implementation Assumptions

- The first user can manually review extracted profile facts
- Initial job sources will be a limited curated set
- English is the primary working language for resume and job text
- Internship postings may be incomplete or noisy, so normalization and deduplication are required
- Tailored resumes can initially be produced from HTML templates rendered to PDF

## Success Criteria

An implementation should be considered successful when it can:

1. Build a verified structured profile from source documents
2. Ingest and normalize internships from multiple sources
3. Rank jobs with interpretable reasons
4. Flag meaningful skill gaps
5. Generate a tailored resume without introducing unverified claims
