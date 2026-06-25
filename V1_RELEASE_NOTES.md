# CareerOS V1 Release Notes

## Summary

CareerOS V1 is a local-first personal internship discovery and career optimization system. It turns verified profile data into internship matches, skill gaps, application tracking, and truthful tailored resume HTML without treating a PDF resume as the source of truth.

## Major Features

- FastAPI backend with PostgreSQL, SQLAlchemy 2.x, Alembic, Docker Compose, and API token protection.
- Profile creation, resume/source-document upload, deterministic text extraction, extraction runs, fact candidates, and evidence spans.
- Claim-level human verification with approved claims and verification events.
- Manual internship ingestion plus real-source adapters for Remotive and Arbeitnow.
- Internship normalization, title/location normalization, skill catalog, skill aliases, and deterministic skill extraction.
- Deterministic and optional sentence-transformers embedding providers.
- Candidate retrieval, hybrid matching, persisted match runs, score components, and deterministic explanations.
- Skill gap analysis, covered skill detection, learning recommendations, and market skill aggregates.
- Truthful tailored resume HTML generation from active approved claims only.
- Lightweight application tracker for saved, applying, applied, interview, rejected, offer, closed, and ignored opportunities.
- Minimal local Vite/React dashboard for matches, applications, and generated resume records.
- Demo, doctor, validation, real-source discovery, reset, and evaluation scripts.
- Reusable `AGENTS.md` and prompt templates for future Codex sessions.

## Architecture Highlights

- Modular monolith: FastAPI application, PostgreSQL database, Docker Compose local runtime, and optional local AI components.
- Structured profile data and approved claims are the source of truth.
- Resume files are source artifacts or generated outputs, not canonical state.
- Career facts flow through extraction, staging, and human verification before downstream use.
- Embeddings are versioned and invalidated rather than silently overwritten.
- Real-source discovery can scope matching to latest-run, source, or all stored internships.
- Localhost-secure defaults are preserved for personal development.

## Supported Sources

- Manual API-submitted internship payloads.
- Remotive public API-style remote jobs feed, filtered for internship, junior, entry-level, graduate, trainee, and associate signals.
- Arbeitnow public API-style job-board feed, filtered with the same deterministic entry-level rules.

## Dashboard Support

The local dashboard in `frontend/` supports:

- Profile ID entry and API connection guidance.
- Top match viewing with scores and missing skills.
- Saving matches or internships into the application tracker.
- Updating application statuses and notes.
- Listing generated resume records and opening resume HTML through the backend.

## Truthful Resume Generation Guarantee

CareerOS V1 generates resume HTML from active approved claims only:

- Pending, rejected, retired, unapproved, and raw candidate text are excluded.
- Rendered claim text is not rewritten by an LLM.
- Every rendered claim is traceable through `generated_resume_claims`.
- The system must not invent experience, skills, projects, dates, metrics, employers, tools, or achievements.

## Known Limitations

- Generated resumes are HTML artifacts; PDF export is not implemented yet.
- Real job quality depends on upstream source feed quality and deterministic filtering.
- Market skill aggregates may need canonical deduplication polish.
- The dashboard is intentionally minimal and local-only.
- There is no auto-apply, cover-letter generation, LinkedIn scraping, public SaaS deployment, or LLM-authored resume content.
- Sentence-transformers embeddings require optional local dependencies and may download/cache the model on first use.

## Future Roadmap Ideas

- Improve source-specific filtering and add more compliant curated sources.
- Add richer ranking evaluation datasets and source-quality diagnostics.
- Add optional local PDF export for generated resumes.
- Improve market intelligence deduplication and trend views.
- Expand the dashboard into a fuller personal workflow shell while keeping local-first privacy.
- Add better profile canonicalization and structured editing after claim approval.
