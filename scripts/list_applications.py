#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.db.models.application import ApplicationStatus  # noqa: E402
from careeros.db.session import create_engine_from_settings, create_session_factory  # noqa: E402
from careeros.services.application_tracker_service import list_profile_applications  # noqa: E402


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description="List tracked CareerOS applications.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--status", choices=[status.value for status in ApplicationStatus])
    parser.add_argument("--priority", type=int, choices=[1, 2, 3, 4, 5])
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL"),
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("No database URL found. Set DATABASE_URL or pass --database-url.")

    settings = Settings(
        database_url=_host_compatible_database_url(args.database_url),
        api_token=os.getenv("API_TOKEN") or env_values.get("API_TOKEN") or "local-script-token",
    )
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            applications = list_profile_applications(
                session=session,
                profile_id=UUID(args.profile_id),
                status_filter=ApplicationStatus(args.status) if args.status else None,
                priority=args.priority,
            )
            rows = [
                [
                    str(application.id),
                    application.status.value,
                    str(application.priority),
                    application.internship.title if application.internship else "-",
                    application.internship.company_name if application.internship else "-",
                    application.next_action_at.isoformat()
                    if application.next_action_at is not None
                    else "-",
                ]
                for application in applications
            ]
            _print_table(
                headers=["id", "status", "priority", "title", "company", "next_action_at"],
                rows=rows,
            )
    finally:
        engine.dispose()
    return 0


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No application records found.")
        return
    widths = [
        min(36, max(len(headers[index]), *(len(row[index]) for row in rows)))
        for index in range(len(headers))
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(
            " | ".join(
                _truncate(value, widths[index]).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return f"{value[: width - 3]}..."


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
