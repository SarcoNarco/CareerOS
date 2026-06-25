#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.core.config import Settings  # noqa: E402
from careeros.db.session import create_engine_from_settings, create_session_factory  # noqa: E402
from careeros.services.embedding_provider import (  # noqa: E402
    EmbeddingProviderUnavailableError,
    build_embedding_provider,
)
from careeros.services.job_discovery_service import (  # noqa: E402
    JobDiscoveryOutcome,
    run_job_discovery,
)
from careeros.services.normalization_seed import ensure_normalization_seed_data  # noqa: E402
from careeros.services.source_adapters import (  # noqa: E402
    SourceAdapterError,
    list_source_adapter_names,
)


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Run real-source job discovery for an approved CareerOS profile."
    )
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--source", required=True, choices=list_source_adapter_names())
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--min-score", type=Decimal, default=None)
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--role-family", choices=["ml", "data", "swe"], default=None)
    parser.add_argument(
        "--scope",
        choices=["latest-run", "source", "all"],
        default="latest-run",
        help=(
            "Which internships to rank. latest-run ranks newly synced postings when "
            "available and falls back to the requested source; source ranks all jobs "
            "from that source; all ranks every stored internship."
        ),
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL"),
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("No database URL found. Set DATABASE_URL or pass --database-url.")
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1.")
    if args.top < 1:
        raise SystemExit("--top must be at least 1.")

    settings = Settings(
        database_url=_host_compatible_database_url(args.database_url),
        api_token=os.getenv("API_TOKEN") or env_values.get("API_TOKEN") or "local-script-token",
    )
    provider = build_embedding_provider(settings)
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            ensure_normalization_seed_data(session)
            outcome = run_job_discovery(
                session=session,
                profile_id=UUID(args.profile_id),
                source_name=args.source,
                limit=args.limit,
                min_score=args.min_score,
                remote_only=args.remote_only,
                role_family=args.role_family,
                provider=provider,
                settings=settings,
                top_matches=args.top,
                scope=args.scope,
            )
            _print_summary(outcome)
    except (EmbeddingProviderUnavailableError, SourceAdapterError) as exc:
        print(f"Job discovery failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    return 0


def _print_summary(outcome: JobDiscoveryOutcome) -> None:
    print("CareerOS job discovery complete")
    print(f"source: {outcome.source_name}")
    print(f"scope: {outcome.scope}")
    print(f"ingestion_run_id: {outcome.ingestion_run_id}")
    print(f"items_seen: {outcome.items_seen}")
    print(f"items_created: {outcome.items_created}")
    print(f"duplicates: {outcome.duplicate_count}")
    print(f"internships_considered: {outcome.internships_considered}")
    print(f"normalized_considered_internships: {outcome.normalized_count}")
    print(f"new_internship_embeddings: {outcome.internship_embeddings_created}")
    print(f"new_profile_embeddings: {outcome.profile_embeddings_created}")
    print(f"match_run_id: {outcome.match_run.id}")
    print(
        "polluted_by_other_sources: "
        f"{'yes' if outcome.polluted_by_other_sources else 'no'}"
    )
    print()

    if not outcome.results:
        print("No matches passed the selected filters.")
        return

    rows = [
        [
            str(result.rank),
            result.internship.title,
            result.internship.company_name,
            f"{float(result.match.total_score):.2f}",
            ", ".join(result.matched_skills) or "-",
            ", ".join(result.missing_skills[:5]) or "-",
            result.internship.application_url,
        ]
        for result in outcome.results
    ]
    _print_table(
        headers=[
            "rank",
            "title",
            "company",
            "score",
            "matched skills",
            "missing skills",
            "application_url",
        ],
        rows=rows,
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
