#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.db.session import create_engine_from_settings, create_session_factory  # noqa: E402
from careeros.services.source_adapters import (  # noqa: E402
    SourceAdapterError,
    list_source_adapter_names,
    sync_source_adapter,
)


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    supported_sources = list_source_adapter_names()
    parser = argparse.ArgumentParser(description="Sync internships from a configured real source.")
    parser.add_argument("--source", required=True, choices=supported_sources)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument(
        "--database-url",
        default=(
            os.getenv("DATABASE_URL")
            or env_values.get("DATABASE_URL")
        ),
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("No database URL found. Set DATABASE_URL or pass --database-url.")
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1.")

    settings = Settings(
        database_url=_host_compatible_database_url(args.database_url),
        api_token=os.getenv("API_TOKEN") or env_values.get("API_TOKEN") or "local-script-token",
    )
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            outcome = sync_source_adapter(
                session=session,
                source_name=args.source,
                limit=args.limit,
            )
    except SourceAdapterError as exc:
        print(f"Source sync failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print("CareerOS source sync complete")
    print(f"source: {args.source}")
    print(f"ingestion_run_id: {outcome.ingestion_run.id}")
    print(f"items_seen: {outcome.ingestion_run.items_seen}")
    print(f"items_created: {outcome.ingestion_run.items_created}")
    print(f"duplicates: {outcome.duplicate_count}")
    if outcome.created_internships:
        print("created_internships:")
        for internship in outcome.created_internships:
            print(f"- {internship.title} at {internship.company_name} ({internship.id})")
    return 0


def _host_compatible_database_url(database_url: str) -> str:
    return database_url.replace("@db:5432", "@127.0.0.1:5432")


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
