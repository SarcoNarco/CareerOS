# Implement Sprint Prompt Template

Use this prompt when implementing a normal CareerOS feature sprint.

## Instructions For The Agent

You are working in the CareerOS / EZJob repository.

Before changing code:

1. Read `AGENTS.md`.
2. Read only the canonical docs needed for this sprint:
   - `docs/PROJECT_CONTEXT.md`
   - `docs/ARCHITECTURE_V2.md`
   - `docs/DECISIONS.md`
   - `docs/ROADMAP.md`
   - `README.md`
3. Inspect relevant existing files before editing.

## Sprint Scope

Implement only the requested sprint:

```text
<PASTE SPRINT GOAL AND REQUIREMENTS HERE>
```

Do not implement adjacent features unless required for acceptance criteria.

## Project Rules

- Structured profile data and approved claims are the source of truth.
- Resume generation must use approved claims only.
- Never use pending, rejected, retired, raw, or unapproved text in generated resumes.
- Do not add auto-apply.
- Do not add LLM-written resume bullets.
- Do not add new infrastructure unless clearly required.
- Prefer vertical slices over broad refactors.
- Keep localhost-secure defaults.
- Do not commit private resume data or secrets.

## Implementation Workflow

1. Identify relevant models, services, schemas, routes, scripts, tests, and docs.
2. Make the smallest coherent code changes.
3. Add or update Alembic migrations for schema changes.
4. Add focused tests for the sprint behavior.
5. Avoid unrelated formatting or refactors.
6. Update docs only when setup, behavior, workflow, or roadmap status changes.

## Verification

Run targeted tests first.

Then run full tests if feasible:

```bash
PYTHONPATH=src .venv/bin/pytest
```

For frontend changes, run:

```bash
cd frontend
npm run build
```

For migration changes, run when feasible:

```bash
alembic upgrade head
```

## Final Response

Report concisely:

- files created or changed
- migrations added
- docs updated
- tests and commands run
- any commands not run and why
- unfinished work or risks
