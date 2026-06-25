# Review Diff Prompt Template

Use this prompt to review a completed CareerOS change.

## Instructions For The Agent

You are reviewing the current repository diff only. Do not rewrite code unless explicitly asked.

Before reviewing:

1. Read `AGENTS.md`.
2. Read only the relevant canonical docs:
   - `docs/PROJECT_CONTEXT.md`
   - `docs/ARCHITECTURE_V2.md`
   - `docs/DECISIONS.md`
   - `docs/ROADMAP.md`
3. Inspect the current diff and touched files.

## Review Priorities

Prioritize bugs, regressions, safety issues, and missing tests over style.

Check for:

- architecture drift from `ARCHITECTURE_V2.md`
- violations of accepted decisions in `docs/DECISIONS.md`
- resume generation using anything except active approved claims
- use of pending, rejected, retired, raw, or unapproved text in generated resumes
- LLM-written resume bullets or unsupported claim rewriting
- auto-apply, email automation, LinkedIn scraping, or autonomous browser agents
- duplicate creation where idempotency is expected
- broken embedding invalidation or stale derived artifacts
- localhost security regressions
- hardcoded secrets or unsafe `.env.example` values
- private resume data or personal files committed
- missing Alembic migrations for schema changes
- missing or weak tests
- stale README, project context, roadmap, or decisions docs
- overengineering or new infrastructure without clear need

## Severity

Classify findings:

- `P0`: blocks safety, data integrity, security, or core workflow correctness.
- `P1`: likely bug, regression, missing migration, or important test gap.
- `P2`: maintainability issue, minor edge case, stale docs, or cleanup.

## Output Format

Findings first, ordered by severity.

For each finding include:

- severity
- file and line reference when possible
- what is wrong
- why it matters
- suggested fix

Then include:

- open questions or assumptions
- tests reviewed or missing
- brief overall assessment

If there are no findings, say that explicitly and note any residual risks.
