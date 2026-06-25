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
14. Skill catalog and skill aliases
15. Normalized title and location lookup tables
16. Deterministic internship skill extraction
17. Internship skill requirement persistence
18. Entity embedding records with content hashes, embedding versions, and invalidation state
19. Embedding rebuild queue processing
20. Semantic candidate internship retrieval from approved claims to internship embeddings
21. Hybrid match runs
22. Persisted internship match scores
23. Structured deterministic match explanations
24. Improved deterministic resume extraction for education, experience, projects, skills, and project/experience claims
25. Extraction diagnostics for section coverage, candidate distribution, claim distribution, quality metrics, and warnings
26. Skill gap analysis for persisted internship matches
27. Deterministic learning recommendations from missing high-demand skills
28. Market skill aggregate endpoints across all internships and by role family
29. Truthful tailored resume generation from approved claims only
30. Generated resume HTML artifacts with claim-level traceability
31. Reproducible V1 end-to-end demo script using safe sample data
32. Safe demo reset tooling for demo-marked records only
33. First real internship source adapter for Remotive's public API-style feed
34. One-command real job discovery pipeline after profile claim approval
35. Lightweight application tracker for saved, active, and archived opportunities
36. Minimal local Vite/React dashboard for matches, applications, and resume outputs
37. Project doctor script for local environment, database, migration, API, storage, embedding, and frontend checks
38. V1 validation script for repeatable backend/demo/embedding/matching/frontend verification
39. Combined real-source discovery check for Remotive and Arbeitnow

Important implementation details for future sessions:

- `source_documents.extracted_text` is populated locally during upload using deterministic extraction
- fact staging is persisted through `extraction_runs`, `fact_candidates`, and `fact_evidence_spans`
- deterministic extraction now uses broader section detection and entity-block grouping for project and experience sections, rather than relying only on blank-line-separated project blocks
- extraction quality diagnostics are stored in `extraction_runs.output_json["diagnostics"]` and exposed through `GET /extraction-runs/{id}/diagnostics`
- diagnostics include detected sections, candidate counts by type, claim counts by source type, quality metrics, and extraction warnings
- skill candidate generation is intentionally bounded to reduce skill-only over-generation before claim review
- claim approval is persisted through `approved_claims` and `verification_events`
- approved claims are now the only persisted text fragments intended for later matching and resume-generation workflows
- manual internship ingestion is implemented through `internship_sources`, `source_policies`, `ingestion_runs`, `raw_postings`, and `internships`
- the manual ingestion API still accepts API-submitted payloads only; real source syncs run through explicit CLI adapters
- `source_adapters.py` defines the first real source adapter interface and registry
- the `remotive` adapter fetches Remotive's public JSON feed with polite headers, preserves raw JSON payloads, and submits parsed postings through `ingestion_service`
- Remotive filtering is deterministic: include internship, junior, entry-level, graduate, trainee, and associate signals; exclude obvious senior, staff, principal, lead, manager, director, head-of, and high-years-of-experience postings
- the `arbeitnow` adapter fetches Arbeitnow's public API-style job-board JSON feed with polite headers, preserves raw JSON payloads, and submits parsed postings through `ingestion_service`
- Arbeitnow filtering uses the same deterministic entry-level inclusion and seniority/high-years exclusion rules as Remotive
- `scripts/sync_source.py --source remotive --limit 25` creates or updates the source and source policy metadata, then runs the existing ingestion pipeline
- `scripts/sync_source.py --source arbeitnow --limit 25` uses the same bounded manual sync path for the second real source
- `scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --limit 25` and `--source arbeitnow --limit 50 --top 10` are the preferred real-job workflows after claims are approved
- job discovery syncs the source, selects internships by scope, normalizes considered internships, embeds considered internships, embeds approved profile claims, recomputes matches, computes gaps for top matches, and prints ranked results
- job discovery supports `--limit`, `--min-score`, `--remote-only`, `--role-family ml|data|swe`, and `--scope latest-run|source|all`
- `scripts/run_job_discovery.py` defaults to `--scope latest-run`, which ranks newly created postings from the current sync when available and falls back to all jobs from the requested source when the latest sync only produced duplicates
- `--scope source` ranks all stored jobs from the requested source; `--scope all` intentionally ranks every stored internship including manual/demo sources
- job discovery output includes source, scope, internships considered, match run, and a `polluted_by_other_sources` flag
- `job_discovery_service.py` keeps the CLI orchestration testable and uses existing source adapter, normalization, embedding, matching, and gap-analysis services
- `scripts/check_sources.py --profile-id <profile_id> --sources remotive arbeitnow --limit 50 --top 10` runs scoped discovery source-by-source and reports counts, top results, and cross-source pollution without printing private resume or claim text
- real-source adapter tests use mocked HTTP responses; the test suite must not depend on live internet
- Sprint 3 ingestion performs lightweight string normalization for title, location, and work mode during ingest
- Sprint 4 structured normalization uses `normalized_titles`, `title_aliases`, and `normalized_locations`, with nullable FK references from `internships`
- skill normalization uses `skill_catalog` and `skill_aliases`; initial seed data is created by migration and idempotent app startup seeding
- the seed catalog includes common AI/ML, data, SWE, frontend, backend, cloud, and DevOps skills such as TypeScript, Node.js, REST APIs, AWS, Kubernetes, Linux, Java, Go, and C++
- deterministic skill extraction writes `internship_skill_requirements` using alias and keyword matching only
- deterministic skill extraction treats real-posting cues such as qualifications, required skills, tech stack, technical skills, and experience-with/in as stronger requirement context
- embeddings are persisted in `entity_embeddings` for approved claims and internships; old active rows are invalidated rather than overwritten
- embedding rebuild work is tracked through `embedding_rebuild_queue`; processing is synchronous in the API/service layer for the MVP
- the default embedding provider is local `sentence-transformers` using `BAAI/bge-small-en-v1.5`, configurable via settings
- `EMBEDDING_PROVIDER=sentence-transformers` is the canonical real local provider value; the legacy alias `sentence_transformers` is normalized for compatibility
- `EMBEDDING_PROVIDER=deterministic` remains available for fast tests, demos, offline checks, and reproducible local development
- sentence-transformers model loading is lazy; configuration can be validated without loading or downloading the model until text is embedded
- `scripts/check_embeddings.py` initializes the configured provider, embeds sample texts, prints dimensions and similarity examples, and fails clearly when local model setup is unavailable
- `scripts/evaluate_matching_quality.py` scores sample ML, Data, Backend, and Frontend internships against sample profile claims and prints ranked score-component tables with pass/fail sanity checks
- tests use a deterministic local embedding provider to avoid model downloads and keep CI lightweight
- candidate retrieval averages approved-claim embeddings for a profile and compares them against active internship embeddings using cosine similarity
- hybrid matching persists `match_runs` and `internship_matches`
- match scoring uses the V2 formula: 40% normalized features, 25% semantic score, 20% skill score, and 15% experience score
- skill gap analysis compares approved profile claims against `internship_skill_requirements`, persists missing skills in `skill_gap_items`, and returns covered skills at response time
- learning recommendations are deterministic and prioritize missing skills that appear in high-scoring matches and broader internship market demand
- market intelligence aggregates distinct internships requiring each skill overall and by normalized role family
- `gap_penalty` is still stored on matches but remains zero until scoring is explicitly revised to include persisted gap severity
- match explanations are deterministic JSON payloads with component scores and matched signals; no LLM explanations are generated
- application tracking is persisted in `application_records` with profile, internship, optional match, status, priority, notes, applied date, and next-action date
- application statuses are `saved`, `applying`, `applied`, `interview`, `rejected`, `offer`, `closed`, and `ignored`
- `POST /applications` returns an existing active record instead of creating duplicates for the same profile and internship
- `DELETE /applications/{id}` archives by setting status to `closed`; it does not hard-delete the workflow record
- `scripts/list_applications.py --profile-id <profile_id>` lists tracked applications with optional `--status` and `--priority` filters
- the local dashboard lives in `frontend/` and uses Vite, React, TypeScript, and minimal CSS
- dashboard configuration is browser-side through `VITE_API_BASE_URL` and `VITE_API_TOKEN`
- FastAPI allows CORS from `http://127.0.0.1:5173` and `http://localhost:5173` for local dashboard development
- dashboard users paste/select a profile ID locally; no new auth flow or SaaS user management exists
- dashboard empty/error states now show API base URL and token guidance so local setup issues are easier to diagnose
- resume generation uses `resume_templates`, `generated_resumes`, and `generated_resume_claims`
- `POST /resumes/generate` selects only active approved claims (`status=approved`, `retired_at is null`) and renders their exact claim text into deterministic HTML
- `GET /profiles/{profile_id}/resumes` lists generated resumes for the dashboard
- `GET /resumes/{resume_id}/html` returns the rendered HTML artifact through token-protected API access
- generated resume claim links persist `approved_claim_id`, section name, display order, and rendered text for every rendered bullet
- the default resume renderer uses a built-in Jinja2 HTML template and writes artifacts under `storage_root/generated_resumes`
- PDF export is intentionally not implemented yet; `rendered_pdf_path` remains null until a reliable local PDF renderer is added
- `scripts/run_v1_demo.py` exercises the full V1 API pipeline using `samples/demo_resume.txt` and `samples/demo_internships.json`
- `scripts/reset_demo_data.py` deletes only demo-marked records and requires `--yes`; it targets `careeros.demo.%@example.test` and `sarosh.e2e.%@example.test` users, `CareerOS Demo Source %` and `Manual E2E Source %` sources, and demo/example source base URLs
- `scripts/doctor.py` checks host local readiness and maps container-style `@db:5432` and `/app/data/incoming` defaults to host-compatible equivalents for diagnostics
- `scripts/validate_v1.py --quick` runs the fast V1 validation path without requiring live internet; full validation adds backend tests, Alembic upgrade, and frontend build unless skipped
- sample data is fictional and safe to commit; do not replace it with private real resume data
- duplicate internship creation is prevented using source-scoped dedupe keys and content hashes
- the system still does not implement LLM explanations, LLM-authored resume bullets, cover letters, auto-apply, or public SaaS UI

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
