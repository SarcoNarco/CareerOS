#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head
exec uvicorn careeros.api.main:create_app --factory --host "${APP_HOST}" --port "${APP_PORT}"
