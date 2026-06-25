# CareerOS

CareerOS is a local-first, AI-assisted career operating system for internship discovery and truthful resume generation.

It is currently a personal system, not a SaaS product. The core safety rule is:

**Generated resumes use approved claims only. CareerOS must not invent experience, skills, metrics, projects, or achievements.**

## Current Capabilities

- Profile creation
- Resume/source document upload
- Deterministic text extraction
- Fact candidates and evidence spans
- Human approval into approved claims
- Manual internship ingestion
- Internship normalization and deterministic skill extraction
- Embeddings and candidate retrieval
- Hybrid matching with score explanations
- Skill gap analysis and learning recommendations
- Truthful tailored HTML resume generation from approved claims only
- Lightweight application tracking for saved/applied/interview/rejected opportunities
- Minimal local React dashboard for matches, applications, and resume outputs
- V1 end-to-end demo script
- Project doctor and V1 validation scripts for fresh local setup checks
- Real-source discovery checks across Remotive and Arbeitnow

## Architecture Summary

CareerOS is a modular monolith:

- `FastAPI` backend
- `PostgreSQL` plus `pgvector` image for storage
- `SQLAlchemy 2.x` ORM
- `Alembic` migrations
- `Docker Compose` local runtime
- Local deterministic embeddings by default for reproducible demos
- Optional sentence-transformers embeddings for richer semantic matching

Data flow:

```text
Profile
→ Resume Upload
→ Extraction
→ Fact Candidates
→ Approved Claims
→ Internship Ingestion
→ Normalization
→ Embeddings
→ Matching
→ Skill Gaps
→ Truthful Resume HTML
```

## Requirements

- Docker and Docker Compose
- Python 3.13
- A local `.env` file

## Environment

Copy the example file:

```bash
cp .env.example .env
```

Important variables:

```text
APP_PORT=8000
API_TOKEN=dev-token
DATABASE_URL=postgresql+psycopg://careeros:replace-with-a-strong-password@db:5432/careeros
POSTGRES_DB=careeros
POSTGRES_USER=careeros
POSTGRES_PASSWORD=replace-with-a-strong-password
STORAGE_ROOT=/app/data/incoming
EMBEDDING_PROVIDER=deterministic
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_VERSION=bge-small-en-v1.5:sentence-transformers:v1
EMBEDDING_DIMENSION=64
```

For the first local demo, keep `EMBEDDING_PROVIDER=deterministic`. This avoids model downloads and makes the demo fast. For real local semantic matching, switch to:

```text
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_VERSION=bge-small-en-v1.5:sentence-transformers:v1
EMBEDDING_DIMENSION=384
```

The legacy value `sentence_transformers` is also accepted, but `sentence-transformers` is the preferred spelling.

## Docker Workflow

Build and start the app:

```bash
docker compose up --build
```

The API is bound to localhost:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

Authenticated endpoints require:

```bash
X-API-Token: dev-token
```

Example:

```bash
curl -s -H "X-API-Token: dev-token" http://127.0.0.1:8000/sources
```

## Migrations

The API container runs migrations on startup via `scripts/start-api.sh`.

You can also run migrations from the host:

```bash
alembic upgrade head
```

When run from the host, Alembic maps the Compose hostname `db` to `127.0.0.1` automatically.

## Local Python Setup

Create and activate a virtual environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install the optional local semantic embedding stack only when you want the
`sentence-transformers` provider:

```bash
pip install -e ".[dev,embeddings]"
```

Run tests:

```bash
pytest
```

## Project Doctor

After creating `.env`, run:

```bash
python scripts/doctor.py
```

The doctor checks Python, required env vars, storage writability, database connectivity, Alembic state, API health when the server is running, embedding configuration, frontend env examples, and Node/npm availability. Results are grouped as `FAIL`, `WARN`, and `PASS` with actionable fixes.

## V1 Validation

Run the fast local validation path:

```bash
python scripts/validate_v1.py --quick
```

Run the fuller validation path:

```bash
python scripts/validate_v1.py
```

Useful flags:

```bash
python scripts/validate_v1.py --quick --skip-frontend
python scripts/validate_v1.py --live-sources
```

Validation runs backend tests and migrations outside `--quick`, demo/help script checks, embedding smoke checks, matching quality evaluation, and the frontend build when the frontend is present. Live source checks are opt-in so the default validation path does not require internet access.

## Embedding Modes

CareerOS supports two local embedding modes:

- `deterministic`: hash-based local vectors for reproducible tests, demos, and offline smoke checks.
- `sentence-transformers`: real local semantic vectors using `BAAI/bge-small-en-v1.5` by default.

No remote embedding or LLM API is required. The first `sentence-transformers` run may download the model into the local Hugging Face cache if it is not already present. After the model is cached, embedding runs locally.

Mac M4 notes:

- Use Python 3.13 for the project environment.
- Install with `pip install -e ".[dev]"` for deterministic mode, or `pip install -e ".[dev,embeddings]"` for the real local embedding provider.
- If `sentence-transformers` or its PyTorch dependency has platform issues, keep `EMBEDDING_PROVIDER=deterministic` until the local ML stack is installed cleanly.
- For the real provider, set `EMBEDDING_DIMENSION=384`; the deterministic demo default uses `64`.

Check the configured provider:

```bash
python scripts/check_embeddings.py
```

Evaluate whether matching behavior is sensible on sample internships:

```bash
python scripts/evaluate_matching_quality.py
```

## Sync Real Internship Sources

CareerOS currently supports two real source adapters:

- `remotive`: fetches Remotive's public API-style remote software jobs feed and filters for internship-like postings.
- `arbeitnow`: fetches Arbeitnow's public API-style job-board feed and filters for internship, junior, and entry-level technical postings.

Run a bounded sync:

```bash
python scripts/sync_source.py --source remotive --limit 25
python scripts/sync_source.py --source arbeitnow --limit 25
```

The sync command:

- creates or updates an `internship_sources` row for the requested source
- stores source policy metadata including policy notes, robot/source notes, and rate-limit notes
- fetches JSON with polite headers
- preserves the raw source payload in `raw_postings`
- passes parsed postings through the existing ingestion, normalization, and dedupe path

Limitations:

- This is a curated API-style adapter, not broad scraping.
- The adapter keeps postings that look internship, junior, entry-level, graduate, trainee, or associate related.
- The adapter excludes obvious senior/staff/principal/lead/manager/director/head roles and postings with high year requirements such as `7+ years`.
- Source policy metadata records that these are API-style JSON feeds synced manually with bounded limits and polite headers.
- Tests use mocked HTTP responses and do not depend on live internet.
- For real profile matching, prefer the one-command discovery workflow below.

## Run Real Job Discovery

After uploading a resume, extracting candidates, and approving claims, run:

```bash
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --limit 25
python scripts/run_job_discovery.py --profile-id <profile_id> --source arbeitnow --limit 50 --top 10
```

The command performs the real-source workflow end to end:

```text
Sync requested source
→ Select internships by discovery scope
→ Normalize considered internships
→ Embed considered internships
→ Embed approved profile claims
→ Recompute matches
→ Compute gaps for top matches
→ Print ranked results
```

By default, discovery uses `--scope latest-run`: it ranks newly created postings from the current sync when available and falls back to all internships from the requested source when the sync only found duplicates. This prevents old demo/manual jobs from dominating real-source discovery.

Useful filters:

```bash
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --limit 25 --remote-only
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --role-family ml
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --min-score 60
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --scope source
python scripts/run_job_discovery.py --profile-id <profile_id> --source remotive --scope all
python scripts/run_job_discovery.py --profile-id <profile_id> --source arbeitnow --limit 50 --top 10
```

Discovery scopes:

- `latest-run`: rank newly created postings from the current sync; if none were created because all were duplicates, rank all jobs from the requested source.
- `source`: rank all stored jobs from the requested source.
- `all`: rank every stored internship, including manual and demo sources. Use this only when you intentionally want a global ranking.

Output includes:

- source and scope used
- internships considered
- whether displayed results include other sources
- rank
- title
- company
- score
- matched skills
- missing skills
- application URL

To compare multiple real sources in one command:

```bash
python scripts/check_sources.py --profile-id <profile_id> --sources remotive arbeitnow --limit 50 --top 10
```

The source check syncs each source, runs scoped discovery, prints per-source counts and top results, and reports whether results are polluted by internships from other sources. It never prints private resume or approved-claim text.

Embedding note:

- `EMBEDDING_PROVIDER=deterministic` is fastest and best for demos/tests.
- `EMBEDDING_PROVIDER=sentence-transformers` gives real local semantic embeddings after the model is installed or cached.

Troubleshooting:

- If the command says no approved claims were found, approve fact candidates first.
- If no matches pass filters, rerun without `--min-score`, `--remote-only`, or `--role-family`.
- If `sentence-transformers` fails to load, switch to `EMBEDDING_PROVIDER=deterministic` or install/cache the local model.
- If Postgres hostname `db` fails from the host, the script maps `@db:5432` to `@127.0.0.1:5432` automatically when using `.env`.

## Run The V1 Demo

Start Docker first:

```bash
docker compose up --build
```

In another terminal, run:

```bash
python scripts/run_v1_demo.py
```

The demo uses safe sample data from:

- `samples/demo_resume.txt`
- `samples/demo_internships.json`

It performs the full V1 workflow:

```text
Create profile
→ Upload sample resume
→ Extract candidates
→ Approve demo candidates
→ Ingest sample internships
→ Normalize internships
→ Embed profile and internships
→ Recompute matches
→ Generate skill gaps
→ Generate truthful resume HTML
→ Print summary
```

Expected output includes:

- profile ID
- extraction run ID
- approved claim count
- created internships
- ranked matches
- skill gap counts
- generated resume ID
- generated resume HTML path

You can override API settings:

```bash
CAREEROS_API_URL=http://127.0.0.1:8000 API_TOKEN=dev-token python scripts/run_v1_demo.py
```

## Reset Demo Data

Dry run:

```bash
python scripts/reset_demo_data.py
```

Delete only demo-marked data:

```bash
python scripts/reset_demo_data.py --yes
```

The reset script only targets:

- users with emails like `careeros.demo.%@example.test`
- users with emails like `sarosh.e2e.%@example.test`
- internship sources with names like `CareerOS Demo Source %`
- internship sources with names like `Manual E2E Source %`
- internship sources using `https://demo.example.test/%` or `https://example.test/%` base URLs

It does not delete arbitrary user data.

## Resume Safety Guarantee

CareerOS resume generation is deterministic and claim-constrained:

- Only `approved_claims` with `status=approved` and `retired_at IS NULL` are eligible.
- Pending, rejected, retired, or unreviewed fact candidates are excluded.
- Rendered resume bullets are exact approved claim text.
- Every rendered bullet is persisted in `generated_resume_claims` with its `approved_claim_id`.
- No LLM writes or rewrites final resume bullets.
- PDF export is not enabled yet; Sprint 8/9 generate HTML artifacts.

## Application Tracker

After job discovery, save an internship or match into the application tracker:

```bash
curl -s -X POST http://127.0.0.1:8000/applications \
  -H "X-API-Token: dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "<profile_id>",
    "internship_id": "<internship_id>",
    "internship_match_id": "<optional_match_id>",
    "status": "saved",
    "priority": 2,
    "notes": "Strong backend fit."
  }'
```

Update status or notes:

```bash
curl -s -X PATCH http://127.0.0.1:8000/applications/<application_id> \
  -H "X-API-Token: dev-token" \
  -H "Content-Type: application/json" \
  -d '{"status": "applied", "notes": "Applied through company site."}'
```

List tracked applications:

```bash
curl -s -H "X-API-Token: dev-token" \
  "http://127.0.0.1:8000/profiles/<profile_id>/applications?status=applied"
```

Or use the local CLI:

```bash
python scripts/list_applications.py --profile-id <profile_id>
python scripts/list_applications.py --profile-id <profile_id> --status interview
python scripts/list_applications.py --profile-id <profile_id> --priority 1
```

Application statuses:

```text
saved, applying, applied, interview, rejected, offer, closed, ignored
```

`DELETE /applications/{id}` archives the record by setting status to `closed`; it does not auto-apply or contact anyone.

## Local Dashboard

The dashboard is a small Vite + React + TypeScript app in `frontend/`.

Create the frontend env file:

```bash
cd frontend
cp .env.example .env
```

Default values:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_TOKEN=dev-token
```

Install and run:

```bash
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Local dashboard workflow:

1. Start the backend with `docker compose up --build`.
2. Run migrations if needed with `alembic upgrade head`.
3. Upload/extract a resume and approve claims.
4. Run job discovery or recompute matches.
5. Paste the profile ID into the dashboard.
6. View top matches, save applications, update statuses/notes, and open generated resume HTML.

Build check:

```bash
cd frontend
npm run build
```

## Useful API Endpoints

```text
GET  /health
POST /profiles
POST /documents/upload
POST /documents/{id}/extract
GET  /profiles/{profile_id}/fact-candidates
POST /fact-candidates/{id}/approve
POST /sources
POST /sources/{id}/ingest
CLI  scripts/sync_source.py --source remotive
CLI  scripts/run_job_discovery.py --profile-id <profile_id> --source remotive
CLI  scripts/check_sources.py --profile-id <profile_id> --sources remotive arbeitnow
CLI  scripts/doctor.py
CLI  scripts/validate_v1.py --quick
POST /internships/{id}/normalize
POST /profiles/{profile_id}/embed
POST /internships/{id}/embed
POST /matches/recompute
GET  /matches/{match_id}/gaps
GET  /profiles/{profile_id}/recommendations
POST /resumes/generate
GET  /profiles/{profile_id}/resumes
GET  /resumes/{resume_id}
GET  /resumes/{resume_id}/html
GET  /resumes/{resume_id}/claims
POST /applications
GET  /profiles/{profile_id}/applications
GET  /applications/{id}
PATCH /applications/{id}
DELETE /applications/{id}
CLI  scripts/list_applications.py --profile-id <profile_id>
```

## Roadmap

CareerOS V1 is now focused on being a complete local-first demoable product: verified profile facts, real-source discovery, scoped matching, skill gaps, truthful resume HTML, application tracking, and a minimal dashboard. Near-term future work should focus on source quality tuning, richer diagnostics, artifact download UX, better profile canonicalization, optional local PDF export, and larger ranking evaluation sets.

## What CareerOS Does Not Do Yet

- No public SaaS frontend
- No auto-apply
- No cover letters
- No external job scraping
- No LLM-authored resume bullets
- No PDF export for generated resumes yet
