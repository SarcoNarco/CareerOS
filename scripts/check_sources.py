#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.db.session import create_engine_from_settings, create_session_factory  # noqa: E402
from careeros.services.embedding_provider import build_embedding_provider  # noqa: E402
from careeros.services.job_discovery_service import JobDiscoveryOutcome, run_job_discovery  # noqa: E402
from careeros.services.normalization_seed import ensure_normalization_seed_data  # noqa: E402
from careeros.services.source_adapters import FetchJson, list_source_adapter_names  # noqa: E402


@dataclass(slots=True)
class SourceCheckResult:
    source: str
    outcome: JobDiscoveryOutcome


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description="Run scoped discovery across multiple sources.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--sources", nargs="+", required=True, choices=list_source_adapter_names())
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--scope", choices=["latest-run", "source", "all"], default="latest-run")
    parser.add_argument("--min-score", type=Decimal, default=None)
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--role-family", choices=["ml", "data", "swe"], default=None)
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
    results = run_source_checks(
        profile_id=UUID(args.profile_id),
        sources=args.sources,
        limit=args.limit,
        top=args.top,
        scope=args.scope,
        min_score=args.min_score,
        remote_only=args.remote_only,
        role_family=args.role_family,
        settings=settings,
    )
    print_source_check_results(results)
    return 0


def run_source_checks(
    *,
    profile_id: UUID,
    sources: list[str],
    limit: int,
    top: int,
    scope: str,
    min_score: Decimal | None,
    remote_only: bool,
    role_family: str | None,
    settings: Settings,
    fetch_json_by_source: dict[str, FetchJson] | None = None,
) -> list[SourceCheckResult]:
    provider = build_embedding_provider(settings)
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    results: list[SourceCheckResult] = []
    try:
        with session_factory() as session:
            ensure_normalization_seed_data(session)
            for source in sources:
                outcome = run_job_discovery(
                    session=session,
                    profile_id=profile_id,
                    source_name=source,
                    limit=limit,
                    min_score=min_score,
                    remote_only=remote_only,
                    role_family=role_family,
                    provider=provider,
                    settings=settings,
                    top_matches=top,
                    scope=scope,  # type: ignore[arg-type]
                    fetch_json=(fetch_json_by_source or {}).get(source),
                )
                results.append(SourceCheckResult(source=source, outcome=outcome))
    finally:
        engine.dispose()
    return results


def print_source_check_results(results: list[SourceCheckResult]) -> None:
    print("CareerOS source discovery check")
    for result in results:
        outcome = result.outcome
        print()
        print(f"source: {result.source}")
        print(f"scope: {outcome.scope}")
        print(f"ingestion_run_id: {outcome.ingestion_run_id}")
        print(f"items_seen: {outcome.items_seen}")
        print(f"items_created: {outcome.items_created}")
        print(f"duplicates: {outcome.duplicate_count}")
        print(f"internships_considered: {outcome.internships_considered}")
        print(f"matches_created: {len(outcome.results)} displayed")
        print(f"polluted_by_other_sources: {'yes' if outcome.polluted_by_other_sources else 'no'}")
        if not outcome.results:
            print("No matches passed the selected filters.")
            continue
        rows = [
            [
                str(item.rank),
                item.internship.title,
                item.internship.company_name,
                f"{float(item.match.total_score):.2f}",
                ", ".join(item.missing_skills[:5]) or "-",
                item.internship.application_url,
            ]
            for item in outcome.results
        ]
        _print_table(
            ["rank", "title", "company", "score", "missing skills", "application_url"],
            rows,
        )


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        min(42, max(len(headers[index]), *(len(row[index]) for row in rows)))
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
