#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import text  # noqa: E402

from careeros.core.config import Settings  # noqa: E402
from careeros.db.session import create_engine_from_settings  # noqa: E402


REQUIRED_ENV_VARS = (
    "API_TOKEN",
    "DATABASE_URL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "STORAGE_ROOT",
)


@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    detail: str
    fix: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local CareerOS developer environment readiness.")
    parser.parse_args()

    env_values = {**_load_env_file(ROOT_DIR / ".env"), **os.environ}
    checks = [
        check_python_version(),
        check_required_env(env_values),
        check_storage(env_values),
        check_embedding_config(env_values),
        check_database(env_values),
        check_alembic_state(env_values),
        check_api_health(env_values),
        check_frontend_env(),
        check_node_tools(),
    ]
    _print_report(checks)
    return 1 if any(check.status == "FAIL" for check in checks) else 0


def check_python_version() -> CheckResult:
    version = sys.version_info
    label = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 13):
        return CheckResult(
            "Python version",
            "FAIL",
            f"Python {label} is running; CareerOS expects Python 3.13+.",
            "Install Python 3.13 and recreate `.venv`.",
        )
    return CheckResult("Python version", "PASS", f"Python {label}")


def check_required_env(env_values: dict[str, str]) -> CheckResult:
    missing = [key for key in REQUIRED_ENV_VARS if not env_values.get(key)]
    if missing:
        return CheckResult(
            "Environment variables",
            "FAIL",
            f"Missing required values: {', '.join(missing)}",
            "Copy `.env.example` to `.env` and fill local values.",
        )
    return CheckResult("Environment variables", "PASS", "Required local env values are present.")


def check_storage(env_values: dict[str, str]) -> CheckResult:
    storage_root = _host_compatible_storage_root(env_values.get("STORAGE_ROOT", "data/incoming"))
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        probe = storage_root / ".doctor-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return CheckResult(
            "Storage directory",
            "FAIL",
            f"{storage_root} is not writable: {exc}",
            "Check `STORAGE_ROOT` permissions or use a project-local path.",
        )
    return CheckResult("Storage directory", "PASS", f"{storage_root} is writable.")


def check_embedding_config(env_values: dict[str, str]) -> CheckResult:
    provider = env_values.get("EMBEDDING_PROVIDER", "sentence-transformers")
    dimension = env_values.get("EMBEDDING_DIMENSION", "")
    if provider not in {"deterministic", "sentence-transformers", "sentence_transformers"}:
        return CheckResult(
            "Embedding configuration",
            "FAIL",
            f"Unsupported EMBEDDING_PROVIDER={provider}",
            "Use `deterministic` or `sentence-transformers`.",
        )
    if not dimension.isdigit() or int(dimension) < 1:
        return CheckResult(
            "Embedding configuration",
            "FAIL",
            f"Invalid EMBEDDING_DIMENSION={dimension!r}",
            "Set a positive integer dimension, e.g. 64 or 384.",
        )
    if provider in {"sentence-transformers", "sentence_transformers"} and int(dimension) == 64:
        return CheckResult(
            "Embedding configuration",
            "WARN",
            "Sentence-transformers usually uses dimension 384; current dimension is 64.",
            "Use 384 for `BAAI/bge-small-en-v1.5`, or deterministic mode for 64.",
        )
    return CheckResult("Embedding configuration", "PASS", f"{provider}, dimension {dimension}")


def check_database(env_values: dict[str, str]) -> CheckResult:
    database_url = env_values.get("DATABASE_URL")
    if not database_url:
        return CheckResult("Database connectivity", "FAIL", "DATABASE_URL is not set.")
    settings = Settings(
        database_url=_host_compatible_database_url(database_url),
        api_token=env_values.get("API_TOKEN", "doctor-token"),
    )
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except Exception as exc:
        return CheckResult(
            "Database connectivity",
            "FAIL",
            f"Could not connect to database: {exc}",
            "Start Postgres with `docker compose up db` or `docker compose up --build`.",
        )
    finally:
        engine.dispose()
    return CheckResult("Database connectivity", "PASS", "Database accepted a simple query.")


def check_alembic_state(env_values: dict[str, str]) -> CheckResult:
    database_url = env_values.get("DATABASE_URL")
    if not database_url:
        return CheckResult("Alembic state", "FAIL", "DATABASE_URL is not set.")
    env = {
        **os.environ,
        "DATABASE_URL": _host_compatible_database_url(database_url),
        "PYTHONPATH": str(SRC_DIR),
    }
    current = _run_command([_python_bin(), "-m", "alembic", "current"], env=env)
    heads = _run_command([_python_bin(), "-m", "alembic", "heads"], env=env)
    if current.returncode != 0:
        return CheckResult(
            "Alembic state",
            "WARN",
            f"Could not inspect current migration: {current.stderr.strip() or current.stdout.strip()}",
            "Run `PYTHONPATH=src .venv/bin/alembic upgrade head`.",
        )
    if heads.returncode != 0:
        return CheckResult(
            "Alembic state",
            "WARN",
            f"Could not inspect migration heads: {heads.stderr.strip() or heads.stdout.strip()}",
            "Run `PYTHONPATH=src .venv/bin/alembic heads`.",
        )
    current_text = current.stdout.strip()
    heads_text = heads.stdout.strip()
    if heads_text and heads_text.split()[0] not in current_text:
        return CheckResult(
            "Alembic state",
            "WARN",
            f"Current revision differs from head. current={current_text}; heads={heads_text}",
            "Run `PYTHONPATH=src .venv/bin/alembic upgrade head`.",
        )
    return CheckResult("Alembic state", "PASS", current_text or "Database is at migration head.")


def check_api_health(env_values: dict[str, str]) -> CheckResult:
    port = env_values.get("APP_PORT", "8000")
    url = f"http://127.0.0.1:{port}/health"
    try:
        with request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, error.URLError, json.JSONDecodeError) as exc:
        return CheckResult(
            "API health",
            "WARN",
            f"API is not reachable at {url}: {exc}",
            "Start it with `docker compose up --build`.",
        )
    if payload.get("status") != "ok":
        return CheckResult("API health", "FAIL", f"Unexpected health payload: {payload}")
    return CheckResult("API health", "PASS", f"{url} returned ok.")


def check_frontend_env() -> CheckResult:
    frontend_dir = ROOT_DIR / "frontend"
    if not frontend_dir.exists():
        return CheckResult("Frontend env", "WARN", "No frontend directory found.")
    example = frontend_dir / ".env.example"
    if not example.exists():
        return CheckResult(
            "Frontend env",
            "WARN",
            "frontend/.env.example is missing.",
            "Add VITE_API_BASE_URL and VITE_API_TOKEN examples.",
        )
    return CheckResult("Frontend env", "PASS", "frontend/.env.example is present.")


def check_node_tools() -> CheckResult:
    if not (ROOT_DIR / "frontend").exists():
        return CheckResult("Node/npm", "WARN", "No frontend directory found.")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node is None or npm is None:
        return CheckResult(
            "Node/npm",
            "WARN",
            "Node.js or npm was not found on PATH.",
            "Install Node.js before running the dashboard.",
        )
    node_version = _run_command([node, "--version"]).stdout.strip()
    npm_version = _run_command([npm, "--version"]).stdout.strip()
    return CheckResult("Node/npm", "PASS", f"node {node_version}, npm {npm_version}")


def _print_report(checks: list[CheckResult]) -> None:
    print("CareerOS doctor")
    for status in ("FAIL", "WARN", "PASS"):
        group = [check for check in checks if check.status == status]
        if not group:
            continue
        print()
        print(status)
        for check in group:
            print(f"- {check.name}: {check.detail}")
            if check.fix:
                print(f"  fix: {check.fix}")


def _run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _python_bin() -> str:
    candidate = ROOT_DIR / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def _host_compatible_database_url(database_url: str) -> str:
    return database_url.replace("@db:5432", "@127.0.0.1:5432")


def _host_compatible_storage_root(storage_root: str) -> Path:
    path = Path(storage_root)
    if storage_root.startswith("/app/data"):
        return ROOT_DIR / "data" / path.relative_to("/app/data")
    return path if path.is_absolute() else ROOT_DIR / path


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
