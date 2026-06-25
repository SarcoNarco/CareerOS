from __future__ import annotations

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from uuid import UUID


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_script_module(name: str):
    path = ROOT_DIR / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"careeros_test_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_sources = _load_script_module("check_sources")
doctor = _load_script_module("doctor")
validate_v1 = _load_script_module("validate_v1")


def _approved_profile(client, auth_headers) -> str:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Completion Test Student",
            "email": "completion-test@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["Machine Learning Intern", "Backend Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]
    resume_text = """PROJECTS
Backend ML Project
- Built Python FastAPI PostgreSQL Docker services and Machine Learning experiments.
"""
    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={"file": ("resume.txt", BytesIO(resume_text.encode("utf-8")), "text/plain")},
    )
    document_id = upload_response.json()["id"]
    client.post(f"/documents/{document_id}/extract", headers=auth_headers)
    candidates_response = client.get(
        f"/profiles/{profile_id}/fact-candidates",
        headers=auth_headers,
    )
    for candidate in candidates_response.json()["items"]:
        if candidate["candidate_kind"] in {"claim", "skill", "project"}:
            client.post(
                f"/fact-candidates/{candidate['id']}/approve",
                headers=auth_headers,
                json={"notes": "Completion script test approval."},
            )
    return profile_id


def _fake_remotive(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": 901,
                "url": "https://remotive.com/remote-jobs/software-dev/ml-intern-901",
                "title": "Machine Learning Intern",
                "company_name": "Completion Remotive",
                "candidate_required_location": "Worldwide",
                "description": "<p>Internship using Python, PyTorch, Pandas, and SQL.</p>",
                "tags": ["python", "pytorch", "pandas", "sql"],
                "category": "Software Development",
            }
        ]
    }


def _fake_arbeitnow(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    return {
        "data": [
            {
                "slug": "junior-backend-python",
                "title": "Junior Backend Python Developer",
                "company_name": "Completion Arbeitnow",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/junior-backend-python",
                "description": "<p>Entry-level Python, FastAPI, PostgreSQL, Docker role.</p>",
                "tags": ["python", "fastapi", "postgresql", "docker"],
                "job_types": ["full-time"],
            }
        ]
    }


def test_doctor_required_env_reports_missing_values() -> None:
    result = doctor.check_required_env({})

    assert result.status == "FAIL"
    assert "API_TOKEN" in result.detail


def test_doctor_embedding_config_accepts_deterministic() -> None:
    result = doctor.check_embedding_config(
        {
            "EMBEDDING_PROVIDER": "deterministic",
            "EMBEDDING_DIMENSION": "64",
        }
    )

    assert result.status == "PASS"


def test_doctor_maps_container_storage_path_to_project_data() -> None:
    storage_root = doctor._host_compatible_storage_root("/app/data/incoming")

    assert storage_root == ROOT_DIR / "data" / "incoming"


def test_validate_quick_steps_skip_slow_checks_and_frontend() -> None:
    steps = validate_v1.build_validation_steps(skip_frontend=True, live_sources=False, quick=True)
    names = {step.name for step in steps}

    assert "backend test suite" not in names
    assert "alembic upgrade head" not in names
    assert "frontend build" not in names
    assert "embedding smoke check" in names


def test_check_sources_runs_mocked_multi_source_discovery(
    client,
    auth_headers,
    app_settings,
) -> None:
    profile_id = _approved_profile(client, auth_headers)

    results = check_sources.run_source_checks(
        profile_id=UUID(profile_id),
        sources=["remotive", "arbeitnow"],
        limit=10,
        top=5,
        scope="latest-run",
        min_score=None,
        remote_only=False,
        role_family=None,
        settings=app_settings,
        fetch_json_by_source={
            "remotive": _fake_remotive,
            "arbeitnow": _fake_arbeitnow,
        },
    )

    assert [result.source for result in results] == ["remotive", "arbeitnow"]
    assert all(result.outcome.results for result in results)
    assert all(not result.outcome.polluted_by_other_sources for result in results)
