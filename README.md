# CareerOS

CareerOS is a local-first career operating system focused on truthful, structured profile management.

This initial vertical slice implements:

- profile creation
- source document upload
- source document metadata persistence
- PostgreSQL-backed FastAPI application

## Quick Start

1. Copy `.env.example` to `.env` and set secure local values.
2. Run `docker compose up --build`.
3. Use the `X-API-Token` header for authenticated endpoints.

