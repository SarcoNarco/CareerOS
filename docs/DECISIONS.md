# CareerOS Architectural Decisions

This file records the major architectural decisions that shape implementation. The goal is to preserve reasoning so future sessions do not depend on prior conversation context.

## Decision 001: Use A Modular Monolith

Date:

2026-06-12

Status:

Accepted

Context:

CareerOS is initially a personal system for one user. The project needs clean internal modularity, but does not need the operational complexity of microservices.

Decision:

Implement CareerOS as a modular monolith with one codebase, one FastAPI API, one PostgreSQL database, and optional background execution paths using the same application package.

Consequences:

- simpler local development and deployment
- fewer infrastructure dependencies
- easier refactoring early on
- future extraction remains possible because internal boundaries are still explicit

## Decision 002: Structured Profile Is The Source Of Truth

Date:

2026-06-12

Status:

Accepted

Context:

The product must never depend on a resume PDF as the canonical user representation.

Decision:

Store career data as structured relational records in PostgreSQL. Resume files are treated as inputs for extraction and outputs for rendering, not as canonical state.

Consequences:

- safe resume regeneration from validated facts
- better querying and explainability
- higher modeling effort up front

## Decision 003: Verification-First Resume Safety Model

Date:

2026-06-12

Status:

Accepted

Context:

The system must never hallucinate experience, skills, achievements, or projects.

Decision:

Every profile fact used in tailored outputs must carry verification state and provenance. In V2, this safety model is enforced at the claim level rather than the record level.

Consequences:

- stronger factual integrity
- need for manual review workflow
- slightly slower profile setup in exchange for trustworthiness

Refined By:

Decision 013 and Decision 015

## Decision 004: PostgreSQL As Primary System Of Record And Vector Store

Date:

2026-06-12

Status:

Accepted

Context:

The project requires structured data, auditability, and embedding-based matching without unnecessary infrastructure.

Decision:

Use PostgreSQL with `pgvector` as both the relational database and the first vector store.

Consequences:

- one operational data platform for MVP
- simpler backups and migrations
- enough semantic search capability for early versions
- may need later reevaluation if scale or retrieval complexity grows significantly

## Decision 005: Use A Postgres-Backed Task Queue For MVP

Date:

2026-06-12

Status:

Superseded

Context:

Background work is needed for parsing, ingestion, embeddings, and match recomputation, but Redis or a broker would add operational overhead early.

Decision:

The original V1 direction was to implement an internal task queue backed by PostgreSQL and processed by a dedicated worker container.

Consequences:

- preserved as a possible future path
- no longer the MVP default after the V2 review

Superseded By:

Decision 012

## Decision 006: Prefer Local-First AI With Provider Abstraction

Date:

2026-06-12

Status:

Accepted

Context:

The project values privacy, cost control, and offline-friendly operation, but may still benefit from optional remote models.

Decision:

Build a thin AI provider abstraction. Prefer local embeddings and local LLMs when practical. Allow optional remote adapters without coupling core logic to a specific provider.

Consequences:

- portability across local and remote providers
- extra adapter design work
- better long-term flexibility

## Decision 007: Use Hybrid Ranking Instead Of Pure Embedding Similarity

Date:

2026-06-12

Status:

Accepted

Context:

Job fit is not reducible to semantic similarity alone. Location, work mode, required skills, and evidence-backed experience matter.

Decision:

Use a hybrid scoring model that combines deterministic rules, structured feature scoring, embeddings, and explicit gap penalties.

Consequences:

- more interpretable ranking
- better control over ranking behavior
- slightly more implementation complexity than nearest-neighbor search alone

## Decision 008: Use Curated Source Adapters, Not Autonomous Browser Agents

Date:

2026-06-12

Status:

Accepted

Context:

The project should avoid brittle, opaque, agentic browsing systems and instead use maintainable ingestion logic.

Decision:

Support job collection through curated adapters using APIs, RSS, or deterministic scrapers. Do not build autonomous browser agents into the MVP.

Consequences:

- easier debugging and compliance review
- smaller operational footprint
- manual maintenance required when sources change

## Decision 009: Store Raw Inputs Alongside Normalized Entities

Date:

2026-06-12

Status:

Accepted

Context:

Extraction and normalization pipelines will evolve. Reprocessing should be possible without recollecting everything from scratch.

Decision:

Persist raw source documents and raw job payloads in addition to normalized entities and extracted facts.

Consequences:

- better auditability and reprocessing support
- larger storage footprint
- clearer provenance across system boundaries

## Decision 010: Generate Resumes From Templates With Traceability

Date:

2026-06-12

Status:

Accepted

Context:

Tailored resumes need to be consistent, reviewable, and fact-constrained.

Decision:

Use deterministic resume templates and persist traceability metadata linking output sections back to source profile entities.

Consequences:

- easier trust and auditability
- predictable output
- less stylistic flexibility than unconstrained free-form generation

## Decision 011: Prepare For Multi-User Mode Without Building It Now

Date:

2026-06-12

Status:

Accepted

Context:

The product is single-user today but may later expand into multi-user mode.

Decision:

Keep `user_id` boundaries in the schema and service design from the beginning, while avoiding full authentication and tenancy complexity in the MVP.

Consequences:

- easier future migration
- small amount of extra modeling now
- avoids reworking core table ownership later

## Decision 012: Remove Mandatory Worker Container From MVP

Date:

2026-06-13

Status:

Accepted

Context:

The original architecture introduced a dedicated worker and queue path too early for a single-user MVP. Most initial workloads are moderate and can be handled synchronously, via FastAPI background tasks, or via explicit CLI commands.

Decision:

The MVP runtime will require only:

- `api`
- `db`
- optional `local-ai`

No dedicated worker container is required in MVP. Background infrastructure should be introduced only if real workload pressure justifies it.

Consequences:

- simpler local deployment
- less operational surface area
- fewer moving parts during early implementation
- long-running jobs may require explicit CLI execution until a worker is justified

## Decision 013: Adopt Claim-Level Verification

Date:

2026-06-13

Status:

Accepted

Context:

Record-level verification is too coarse to satisfy the requirement that the system never hallucinate resume content. Free-text fields inside a verified record can still contain unsupported claims.

Decision:

Verification will operate at the atomic claim level. Only approved claims may be used in tailored resume outputs.

Consequences:

- stronger factual integrity
- more review structure is required
- resume generation becomes much safer and easier to audit

## Decision 014: Introduce A Fact Staging Pipeline

Date:

2026-06-13

Status:

Accepted

Context:

The extraction flow needs a real staging area between AI output and canonical profile data.

Decision:

Add staged extraction tables and review flow:

- `extraction_runs`
- `fact_candidates`
- `fact_evidence_spans`
- `verification_events`

AI-extracted facts must be reviewed before promotion into canonical entities or approved claims.

Consequences:

- better auditability
- easier correction and reprocessing
- slightly more schema and workflow complexity in exchange for safety

## Decision 015: Generate Resumes From Approved Claims Only

Date:

2026-06-13

Status:

Accepted

Context:

Even with structured profile records, allowing an LLM to freely rewrite resume bullets creates an unacceptable hallucination risk.

Decision:

The MVP resume pipeline will assemble resumes from approved claims only. AI may help rank or classify claims, but it will not author final resume bullets in the MVP path.

Consequences:

- output is more trustworthy
- traceability becomes straightforward
- resume wording may be less flexible until later controlled rewriting rules are introduced

## Decision 016: Add Deterministic Normalization Before Embedding Matching

Date:

2026-06-13

Status:

Accepted

Context:

Pure semantic similarity is too noisy when raw titles, skills, and locations are inconsistent.

Decision:

Add a first-class normalization layer for:

- skills
- titles
- locations

Matching will run deterministic normalized scoring before embedding reranking.

Consequences:

- better precision in ranking
- more interpretable matching behavior
- some up-front taxonomy maintenance is required

## Decision 017: Make Localhost Security The Default Posture

Date:

2026-06-13

Status:

Accepted

Context:

Local-first systems still process sensitive data and must not rely on insecure defaults.

Decision:

The default local deployment must:

- bind services to localhost
- avoid hardcoded secrets in Compose
- require local credentials or token-based access
- exclude sensitive document contents from routine logs and public serialization

Consequences:

- safer out-of-the-box setup
- slightly more setup work for local development
- reduces accidental data exposure risk

## Decision 018: Add Explicit Embedding Invalidation And Versioning

Date:

2026-06-13

Status:

Accepted

Context:

Embeddings become stale when content, normalization rules, or models change. The V1 schema did not define a safe lifecycle for this.

Decision:

Store embeddings with content hashes, version metadata, and invalidation markers. Rebuilds should be explicitly queued in database tables rather than silently overwriting prior vectors.

Consequences:

- safer and more reproducible ranking behavior
- better auditability of model-driven artifacts
- slightly more bookkeeping in the data model

## Decision 019: Store MVP Embeddings As Portable JSON Vectors

Date:

2026-06-18

Status:

Accepted

Context:

The long-term architecture uses PostgreSQL with `pgvector`, and the Docker database image already supports it. The current MVP test harness also runs against SQLite, and the first retrieval slice does not need database-side approximate nearest-neighbor search.

Decision:

Persist embedding vectors as JSON lists in `entity_embeddings` for the first candidate retrieval implementation. Compute cosine similarity in the application service layer. Preserve the same lifecycle fields required by V2:

- `content_hash`
- `model_name`
- `embedding_version`
- `is_active`
- `invalidated_at`
- `invalidation_reason`

Consequences:

- keeps tests and local development portable
- avoids introducing extra Python vector-store dependencies before scale requires them
- makes candidate retrieval adequate for a personal MVP dataset
- can later migrate the `embedding` column to `pgvector` and push similarity search into PostgreSQL without changing API semantics
