from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def _create_demo_cleanup_db(path: Path) -> str:
    database_url = f"sqlite+pysqlite:///{path}"
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(text("create table users (id text primary key, email text not null)"))
        connection.execute(text("create table profiles (id text primary key, user_id text not null)"))
        connection.execute(
            text("create table internship_sources (id text primary key, name text not null, base_url text)")
        )
        connection.execute(
            text("create table internships (id text primary key, source_id text not null)")
        )
        connection.execute(
            text(
                "insert into users (id, email) values "
                "('demo-user', 'careeros.demo.123@example.test'), "
                "('e2e-user', 'sarosh.e2e.123@example.test'), "
                "('real-user', 'real@example.com')"
            )
        )
        connection.execute(
            text(
                "insert into profiles (id, user_id) values "
                "('demo-profile', 'demo-user'), "
                "('real-profile', 'real-user')"
            )
        )
        connection.execute(
            text(
                "insert into internship_sources (id, name, base_url) values "
                "('demo-source', 'CareerOS Demo Source 123', 'https://demo.example.test/'), "
                "('e2e-source', 'Manual E2E Source 123', 'https://example.test/careeros-e2e'), "
                "('real-source', 'Real Source', 'https://real.example.com')"
            )
        )
        connection.execute(
            text(
                "insert into internships (id, source_id) values "
                "('demo-job', 'demo-source'), "
                "('real-job', 'real-source')"
            )
        )
    engine.dispose()
    return database_url


def test_reset_demo_data_dry_run_does_not_delete_rows(tmp_path: Path) -> None:
    database_url = _create_demo_cleanup_db(tmp_path / "cleanup.db")

    result = subprocess.run(
        [sys.executable, "scripts/reset_demo_data.py", "--database-url", database_url],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Dry run only" in result.stdout
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from users")) == 3
        assert connection.scalar(text("select count(*) from internship_sources")) == 3
    engine.dispose()


def test_reset_demo_data_yes_keeps_real_rows(tmp_path: Path) -> None:
    database_url = _create_demo_cleanup_db(tmp_path / "cleanup.db")

    subprocess.run(
        [sys.executable, "scripts/reset_demo_data.py", "--database-url", database_url, "--yes"],
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        remaining_users = set(connection.scalars(text("select email from users")))
        remaining_sources = set(connection.scalars(text("select name from internship_sources")))
    engine.dispose()

    assert remaining_users == {"real@example.com"}
    assert remaining_sources == {"Real Source"}
