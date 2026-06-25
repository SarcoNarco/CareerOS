# Release Check Prompt Template

Use this prompt to verify whether CareerOS is ready to commit, demo, or hand off.

## Instructions For The Agent

You are checking repository readiness, not implementing product features.

Before running checks:

1. Read `AGENTS.md`.
2. Read only the canonical docs needed to verify readiness:
   - `docs/PROJECT_CONTEXT.md`
   - `docs/ARCHITECTURE_V2.md`
   - `docs/DECISIONS.md`
   - `docs/ROADMAP.md`
   - `README.md`
3. Inspect the current diff and untracked files.

Do not modify code unless the user explicitly asks for fixes.

## Required Checks

Verify the repository against these areas:

- Backend tests pass with `PYTHONPATH=src .venv/bin/pytest`.
- Migrations apply cleanly with `alembic upgrade head`.
- Relevant demo/help scripts still run or at least expose valid help output.
- Frontend builds with `npm run build` from `frontend/` if a frontend exists.
- No private resume data, personal files, secrets, `.env`, API tokens, or credentials are staged or committed.
- No hardcoded secrets were introduced.
- `.env.example` remains safe and contains placeholder/local-only values.
- `README.md` accurately describes setup, environment variables, tests, demos, and workflows.
- `docs/PROJECT_CONTEXT.md` and `docs/ROADMAP.md` are updated when behavior, setup, or roadmap status changed.
- Resume safety rules remain intact: generated resumes must use active approved claims only.

## Suggested Commands

Adjust commands only when the local environment requires it.

```bash
git status --short
git diff --stat
git diff --check
PYTHONPATH=src .venv/bin/pytest
alembic upgrade head
python scripts/run_v1_demo.py --help
python scripts/sync_source.py --help
python scripts/run_job_discovery.py --help
python scripts/list_applications.py --help
test ! -d frontend || (cd frontend && npm run build)
```

Use targeted searches for sensitive data:

```bash
git ls-files --others --exclude-standard
rg -n "BEGIN (RSA|OPENSSH|PRIVATE) KEY|api[_-]?key|secret|password|token" .
rg -n "resume|cv|curriculum vitae" samples docs README.md scripts tests
```

When searching, avoid reporting benign placeholders as failures if they are clearly safe examples.

## Output Format

Produce a concise readiness report:

- `Summary`: pass or fail, with one sentence explaining the state.
- `Commands Run`: command and result for each check.
- `Failures`: concrete blockers or warnings, with file references when relevant.
- `Recommended Next Action`: the single next step, such as commit, fix blockers, update docs, or rerun a failed command.

If a command cannot be run, mark it as not run, explain why, and state what remains unverified.
