# CareerOS Agent Instructions

## Project Summary

CareerOS is a local-first personal internship discovery and career optimization system for one primary user: a Computer Science student targeting ML, AI, Data Science, and Software Engineering internships in India and worldwide remote roles.

The project is not a SaaS product. Optimize for correctness, privacy, truthful career data, maintainability, and fast personal iteration.

## Canonical Read Order

Before meaningful implementation work, read only the context needed for the task, starting here:

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/ARCHITECTURE_V2.md`
4. `docs/DECISIONS.md`
5. `docs/ROADMAP.md`
6. `README.md`

Prefer these files over conversation memory. Keep future docs sufficient for reconstructing project context.

## Core Architecture Rules

- Structured profile data and approved claims are the source of truth.
- A PDF resume is an input/output artifact, not canonical state.
- Career facts must flow through staging and verification before trusted downstream use.
- Approved claims are the only text fragments eligible for matching, skill-gap analysis, and resume generation.
- Prefer deterministic logic before generative AI.
- Keep the MVP as a modular monolith: FastAPI, PostgreSQL, Docker Compose, and optional local AI.
- Do not add new infrastructure unless a task clearly requires it.
- Prefer vertical slices over broad refactors.
- Preserve localhost-secure defaults.

## Resume Safety Rules

- Resume generation must use approved claims only.
- Never use pending, rejected, retired, unapproved, or raw candidate text in generated resumes.
- Never invent experience, skills, metrics, projects, achievements, education, employers, dates, or tools.
- Do not add LLM-written resume bullets.
- Do not merge claims into stronger unsupported claims.
- Preserve claim-level traceability for generated resume content.

## Product Safety Rules

- Do not add auto-apply.
- Do not add email automation.
- Do not add cover letters unless explicitly requested.
- Do not scrape LinkedIn.
- Do not introduce autonomous browser agents.
- Do not commit private resume data, personal files, secrets, `.env`, API tokens, or credentials.
- Keep sample data fictional and safe to commit.

## Implementation Rules

- Identify relevant files before editing.
- Avoid unrelated refactors and broad rewrites.
- Use existing services, schemas, and routes where practical.
- Keep changes MVP-focused.
- Maintain type hints in Python.
- Add Alembic migrations for database schema changes.
- Keep API token protection on non-public endpoints.
- For frontend work, keep the dashboard local and simple unless explicitly asked otherwise.

## Testing Expectations

- Run targeted tests for the changed area first.
- Run the full backend test suite when feasible: `PYTHONPATH=src .venv/bin/pytest`.
- For frontend changes, run `npm run build` from `frontend/` when dependencies are available.
- For migrations, verify `alembic upgrade head` when feasible.
- If a command cannot be run, report why and what remains unverified.

## Documentation Expectations

Update docs only when behavior, setup, architecture, workflow, or roadmap status changes.

Common docs:

- `README.md` for setup and user/developer workflows.
- `docs/PROJECT_CONTEXT.md` for durable implementation context future agents need.
- `docs/ROADMAP.md` for completed or pending roadmap status.
- `docs/DECISIONS.md` only for new architectural decisions, not routine implementation details.

## Forbidden Unless Explicitly Requested

- Do not change product architecture casually.
- Do not add new infrastructure, queues, services, or external providers without need.
- Do not replace the verification-first resume safety model.
- Do not weaken localhost or API-token security defaults.
- Do not hardcode credentials.
- Do not commit private user resume data.
- Do not perform destructive git operations.
