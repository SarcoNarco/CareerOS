# CareerOS Roadmap

## Planning Principles

The roadmap is optimized for:

- fast delivery of a useful personal system
- correctness over feature breadth
- local-first operation where practical
- minimal infrastructure
- explicit checkpoints for data quality and factual safety

## MVP Scope

The MVP includes:

1. One local user profile
2. Resume and source-document import
3. Structured fact extraction with manual verification
4. Internship ingestion from a limited set of curated sources
5. Deduplication and normalized internship storage
6. Embedding-assisted ranking with deterministic score breakdown
7. Human-readable explanation and skill-gap analysis
8. Tailored resume generation from verified facts only
9. Docker Compose-based local deployment

The MVP excludes:

- multi-user auth
- browser automation
- autonomous application submission
- advanced frontend product design
- large-scale analytics
- interview coaching
- cover letter generation as a primary workflow

## Phase 0: Project Foundation

Goal:

Create the implementation skeleton and development standards.

Deliverables:

- repository scaffold
- FastAPI app bootstrapped
- PostgreSQL and Docker Compose wiring
- SQLAlchemy and Alembic setup
- linting, typing, tests, pre-commit
- docs baseline from `docs/`

Acceptance criteria:

- `docker compose up` starts API and database
- health endpoint works
- migrations can be applied cleanly
- test harness runs locally

## Phase 1: Structured Career Profile

Goal:

Make the profile system real before tackling matching.

Deliverables:

- schema for profile, documents, skills, education, experience, projects
- document upload and storage paths
- PDF text extraction
- structured extraction pipeline to typed JSON
- verification workflow for facts
- CRUD APIs for profile records

Acceptance criteria:

- a master resume can be imported
- extracted facts land in the database as pending or verified entities
- the user can correct and verify facts
- the canonical profile can be reconstructed from database records alone

Implementation status:

- Completed: profile creation, resume upload, source document persistence
- Completed: deterministic extraction runs, fact candidates, and evidence spans
- Completed: verification and claim promotion pipeline with approved claims and verification events
- Completed quality pass: richer deterministic extraction for education, experience, projects, skills, and project/experience claims
- Completed quality pass: extraction diagnostics endpoint for section coverage, candidate distribution, claim distribution, quality metrics, and warnings
- Pending within broader phase: richer profile canonicalization beyond staging, additional source parsing coverage

## Phase 2: Internship Ingestion

Goal:

Build the opportunity pipeline with a small set of reliable sources.

Suggested starting sources:

- LinkedIn only if a stable compliant approach exists
- company career pages for target employers
- Wellfound
- Internshala or similar India-focused boards if allowed and maintainable
- curated RSS or API-based sources where possible

Deliverables:

- source registry
- ingestion adapters
- raw payload storage
- normalized internship model
- deduplication strategy
- scheduled sync jobs

Acceptance criteria:

- at least 2 to 4 sources ingest successfully
- duplicate listings collapse into one canonical posting
- posting provenance remains traceable

Implementation status:

- Completed foundation: manual source registry
- Completed foundation: API-submitted manual internship payload ingestion
- Completed foundation: ingestion runs, raw postings, normalized internships, and duplicate prevention
- Completed foundation: structured title and location normalization tables
- Completed foundation: initial skill catalog, skill aliases, and deterministic internship skill extraction
- Completed foundation: internship skill requirement persistence and read API
- Completed foundation: first real curated source adapter for Remotive's public API-style feed via `scripts/sync_source.py`
- Completed foundation: second real curated source adapter for Arbeitnow's public API-style job-board feed via `scripts/sync_source.py`
- Completed workflow pass: one-command real job discovery via `scripts/run_job_discovery.py`
- Completed quality pass: source/latest-run scoped discovery prevents stale demo/manual jobs from dominating real-source rankings
- Completed quality pass: Remotive deterministic filtering excludes obvious senior/staff/non-entry roles and includes intern/junior/entry-level signals
- Pending within broader phase: additional compliant source adapters, scheduled sync jobs, and source-specific quality tuning

## Phase 3: Matching And Ranking

Goal:

Turn stored jobs into useful prioritized recommendations.

Deliverables:

- embedding pipeline
- skill extraction from job descriptions
- hybrid scoring engine
- persisted match runs
- explanation payload generation
- skill-gap records

Acceptance criteria:

- the system can rank postings for the profile
- each ranking contains interpretable score components
- at least basic gap analysis is visible per match

Implementation status:

- Completed foundation: local embedding provider abstraction with sentence-transformers default
- Completed foundation: approved-claim and internship embedding creation
- Completed foundation: embedding content hashes, versions, invalidation metadata, and rebuild queue
- Completed foundation: semantic candidate internship retrieval using cosine similarity
- Completed quality pass: real local `sentence-transformers` provider setup with deterministic fallback, lazy loading, provider smoke checks, and matching quality evaluation tooling
- Completed foundation: hybrid scoring engine using the V2 weighted formula
- Completed foundation: persisted match runs and internship match results
- Completed foundation: deterministic structured score explanations
- Completed foundation: persisted `skill_gap_items` for missing skills per internship match
- Completed foundation: deterministic covered-skill detection, profile skill-gap listing, learning recommendations, and market top-skill aggregates
- Completed workflow pass: real-source discovery now normalizes jobs, embeds jobs/profile claims, recomputes matches, computes gaps, and prints ranked results from one command
- Pending within broader phase: richer explanation surfaces, source-specific ranking tuning, larger labeled ranking evaluation sets, and optional scoring integration for gap penalties

## Phase 4: Tailored Resume Generation

Goal:

Produce truthful, targeted resumes from verified data.

Deliverables:

- resume template model
- relevance-based fact selection
- section traceability metadata
- HTML and PDF rendering
- artifact storage and retrieval

Acceptance criteria:

- a targeted resume can be generated for a chosen internship
- every rendered bullet can be traced to verified source facts
- no unverified facts appear in output

Implementation status:

- Completed foundation: resume template, generated resume, and generated resume claim traceability tables
- Completed foundation: deterministic claim selection from active approved claims only
- Completed foundation: Jinja2 HTML resume rendering with one trace row per rendered claim
- Pending within broader phase: richer editable templates, PDF export, resume artifact retrieval/download UX, and final human approval workflow

## Phase 5: Workflow Hardening

Goal:

Improve reliability, observability, and usability.

Deliverables:

- better error reporting
- ingestion retry and backoff
- admin endpoints or simple UI for reviewing runs
- improved logs and metrics
- dataset cleanup scripts

Acceptance criteria:

- failures are diagnosable
- reruns are safe
- common maintenance tasks are scripted

Implementation status:

- Completed foundation: V1 end-to-end demo script using safe local sample data
- Completed foundation: fictional sample resume and internship fixtures
- Completed foundation: full-pipeline smoke test covering profile through truthful resume generation
- Completed foundation: guarded demo reset script for demo-marked records only
- Completed quality pass: demo reset now reports users, profiles, sources, and internships and also targets manual E2E/example-test pollution safely
- Completed foundation: README developer guide for setup, Docker, migrations, tests, demo, API tokens, and resume safety guarantees
- Completed workflow pass: lightweight application tracker with save, status updates, notes, filters, and archive behavior
- Completed usability pass: minimal local Vite/React dashboard for matches, applications, and resume outputs
- Completed completion pass: project doctor, V1 validation script, combined real-source discovery check, dashboard setup guidance, and GitHub-ready README polish
- Pending within broader phase: artifact download UX, source-specific ingestion maintenance scripts, deeper source quality tuning, and production hardening

## Recommended Delivery Sequence

1. Foundation
2. Profile system
3. Ingestion
4. Matching
5. Resume generation
6. Hardening

This order matters because the structured profile is the prerequisite for safe matching and tailored resume generation.

## Future Roadmap

### Stage 2: Better Intelligence

- local LLM prompt tuning for extraction and explanations
- model evaluation harness for ranking quality
- improved semantic retrieval over projects and coursework
- stronger gap remediation suggestions

### Stage 3: Career Operating System Expansion

- richer application tracker views and reminders
- company watchlists
- saved search presets
- outreach and networking notes
- interview preparation artifacts

### Stage 4: Multi-User Readiness

- authentication and authorization
- tenant-aware storage and retrieval
- user isolation tests
- admin controls

### Stage 5: Optional Service Extraction

Only consider this if the modular monolith becomes operationally limiting.

Possible extraction candidates:

- ingestion worker
- embedding service
- document rendering service

This should not happen before there is clear evidence of scale or maintenance pain.

## Open Questions To Revisit Later

- which exact job sources are compliant and maintainable long-term
- whether remote fallback LLMs are acceptable for personal usage
- whether resume generation should eventually support DOCX export
- whether the local dashboard should remain developer-only or become a fuller personal app shell

## Definition Of Done For Version 1

Version 1 is complete when CareerOS can:

1. store a verified structured candidate profile
2. ingest fresh internships from multiple sources
3. rank internships with reasons
4. identify missing skills
5. generate a truthful tailored resume from verified facts
6. run locally via Docker Compose without depending on conversation memory
