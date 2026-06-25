#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text


ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_EMAIL_PATTERNS = (
    "careeros.demo.%@example.test",
    "sarosh.e2e.%@example.test",
)
DEMO_SOURCE_NAME_PATTERNS = (
    "CareerOS Demo Source %",
    "Manual E2E Source %",
)
DEMO_SOURCE_BASE_URL_PATTERNS = (
    "https://demo.example.test/%",
    "https://example.test/%",
)


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Safely remove only CareerOS V1 demo records."
    )
    parser.add_argument(
        "--database-url",
        default=(
            os.getenv("DEMO_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or env_values.get("DEMO_DATABASE_URL")
            or env_values.get("DATABASE_URL")
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete demo records. Without this flag the script only prints counts.",
    )
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("No database URL found. Set DATABASE_URL or pass --database-url.")

    database_url = _host_compatible_database_url(args.database_url)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        user_where, user_params = _like_where("email", DEMO_EMAIL_PATTERNS, "email")
        source_name_where, source_name_params = _like_where(
            "name",
            DEMO_SOURCE_NAME_PATTERNS,
            "source_name",
        )
        source_url_where, source_url_params = _like_where(
            "coalesce(base_url, '')",
            DEMO_SOURCE_BASE_URL_PATTERNS,
            "source_url",
        )
        source_where = f"({source_name_where}) or ({source_url_where})"
        source_params = {**source_name_params, **source_url_params}

        user_count = connection.scalar(
            text(f"select count(*) from users where {user_where}"),
            user_params,
        )
        profile_count = connection.scalar(
            text(
                "select count(*) from profiles p join users u on u.id = p.user_id "
                f"where {user_where}"
            ),
            user_params,
        )
        source_count = connection.scalar(
            text(f"select count(*) from internship_sources where {source_where}"),
            source_params,
        )
        internship_count = connection.scalar(
            text(
                "select count(*) from internships i "
                "join internship_sources s on s.id = i.source_id "
                f"where {source_where}"
            ),
            source_params,
        )
        print(f"Demo users matched: {user_count}")
        print(f"Demo profiles matched: {profile_count}")
        print(f"Demo internship sources matched: {source_count}")
        print(f"Demo internships matched: {internship_count}")

        if not args.yes:
            print("Dry run only. Re-run with --yes to delete demo records.")
            return 0

        connection.execute(
            text(f"delete from users where {user_where}"),
            user_params,
        )
        connection.execute(
            text(f"delete from internship_sources where {source_where}"),
            source_params,
        )
        print("Deleted demo records. Cascading foreign keys removed associated demo rows.")
    return 0


def _host_compatible_database_url(database_url: str) -> str:
    # `.env` is container-oriented by default (`@db:5432`). For host-run maintenance
    # scripts, map the Compose service hostname to the localhost-bound Postgres port.
    return database_url.replace("@db:5432", "@127.0.0.1:5432")


def _like_where(column_sql: str, patterns: tuple[str, ...], prefix: str) -> tuple[str, dict[str, str]]:
    clauses: list[str] = []
    params: dict[str, str] = {}
    for index, pattern in enumerate(patterns):
        key = f"{prefix}_{index}"
        clauses.append(f"{column_sql} like :{key}")
        params[key] = pattern
    return " or ".join(clauses), params


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
