#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import error, parse, request


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESUME_PATH = ROOT_DIR / "samples" / "demo_resume.txt"
DEFAULT_INTERNSHIPS_PATH = ROOT_DIR / "samples" / "demo_internships.json"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEMO_EMAIL_DOMAIN = "example.test"


class DemoClient:
    def __init__(self, api_url: str, api_token: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token

    def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        url = f"{self.api_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"
        return self._request("GET", url)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload or {}).encode("utf-8")
        return self._request(
            "POST",
            f"{self.api_url}{path}",
            body=body,
            headers={"Content-Type": "application/json"},
        )

    def upload_document(self, *, profile_id: str, resume_path: Path) -> dict[str, Any]:
        boundary = f"----CareerOSDemo{uuid.uuid4().hex}"
        body = _multipart_body(
            boundary=boundary,
            fields={
                "profile_id": profile_id,
                "document_type": "resume",
            },
            file_field="file",
            file_path=resume_path,
            content_type="text/plain",
        )
        return self._request(
            "POST",
            f"{self.api_url}/documents/upload",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    def _request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"X-API-Token": self.api_token}
        request_headers.update(headers or {})
        req = request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with request.urlopen(req, timeout=120) as response:
                data = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed with {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
        if not data:
            return {}
        return json.loads(data)


def main() -> int:
    env_values = _load_env_file(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description="Run the CareerOS V1 end-to-end demo.")
    parser.add_argument("--api-url", default=os.getenv("CAREEROS_API_URL", DEFAULT_API_URL))
    parser.add_argument(
        "--api-token",
        default=os.getenv("API_TOKEN") or env_values.get("API_TOKEN") or "dev-token",
    )
    parser.add_argument("--resume-path", type=Path, default=DEFAULT_RESUME_PATH)
    parser.add_argument("--internships-path", type=Path, default=DEFAULT_INTERNSHIPS_PATH)
    parser.add_argument("--max-claims", type=int, default=18)
    parser.add_argument("--json", action="store_true", help="Print only the final JSON summary.")
    args = parser.parse_args()

    client = DemoClient(api_url=args.api_url, api_token=args.api_token)
    run_id = str(int(time.time()))
    resume_path = args.resume_path.resolve()
    internships_path = args.internships_path.resolve()
    if not resume_path.exists():
        raise SystemExit(f"Sample resume not found: {resume_path}")
    if not internships_path.exists():
        raise SystemExit(f"Sample internships not found: {internships_path}")

    postings = json.loads(internships_path.read_text(encoding="utf-8"))
    _log(args, "Checking API health")
    health = client.get("/health")

    _log(args, "Creating demo profile")
    profile = client.post(
        "/profiles",
        {
            "display_name": "CareerOS Demo Student",
            "email": f"careeros.demo.{run_id}@{DEMO_EMAIL_DOMAIN}",
            "timezone": "Asia/Kolkata",
            "headline": "Computer Science student exploring AI, data, and software internships",
            "target_roles": [
                "Machine Learning Intern",
                "Data Science Intern",
                "Backend Intern",
                "Software Engineering Intern",
            ],
            "target_locations": ["Remote", "India"],
            "work_preferences": {"demo_run_id": run_id},
        },
    )
    profile_id = profile["id"]

    _log(args, "Uploading sample resume")
    document = client.upload_document(profile_id=profile_id, resume_path=resume_path)

    _log(args, "Extracting fact candidates")
    extraction = client.post(f"/documents/{document['id']}/extract")
    candidates = client.get(f"/profiles/{profile_id}/fact-candidates")["items"]
    approvable_kinds = {"education", "experience", "project", "skill", "claim"}
    pending_candidates = [
        item
        for item in candidates
        if item["status"] == "pending" and item["candidate_kind"] in approvable_kinds
    ]

    _log(args, f"Approving {len(pending_candidates)} demo candidates")
    approved_count = 0
    for candidate in pending_candidates:
        client.post(
            f"/fact-candidates/{candidate['id']}/approve",
            {"notes": "Approved automatically for the safe local V1 demo."},
        )
        approved_count += 1

    _log(args, "Creating manual demo source")
    source = client.post(
        "/sources",
        {
            "name": f"CareerOS Demo Source {run_id}",
            "source_type": "manual",
            "base_url": "https://demo.example.test",
            "is_active": True,
            "policy_status": "allowed",
            "policy_notes": "Safe local demo fixture data only.",
        },
    )

    _log(args, "Ingesting sample internships")
    demo_postings = [_with_run_suffix(posting, run_id) for posting in postings]
    ingestion = client.post(f"/sources/{source['id']}/ingest", {"postings": demo_postings})
    internships = ingestion["created_internships"]

    _log(args, "Normalizing and embedding internships")
    for internship in internships:
        client.post(f"/internships/{internship['id']}/normalize")
        client.post(f"/internships/{internship['id']}/embed")

    _log(args, "Embedding profile claims")
    profile_embeddings = client.post(f"/profiles/{profile_id}/embed")
    rebuild = client.post("/embeddings/rebuild", {"process": True, "limit": 200})

    _log(args, "Recomputing matches")
    matches_response = client.post("/matches/recompute", {"profile_id": profile_id})
    demo_internship_ids = {item["id"] for item in internships}
    demo_matches = [
        item for item in matches_response["matches"]
        if item["internship_id"] in demo_internship_ids
    ]
    demo_matches.sort(key=lambda item: float(item["total_score"]), reverse=True)
    if not demo_matches:
        raise RuntimeError("No demo matches were returned.")
    top_match = demo_matches[0]

    _log(args, "Computing gaps and recommendations")
    gaps = client.get(f"/matches/{top_match['id']}/gaps")
    profile_gaps = client.get(f"/profiles/{profile_id}/skill-gaps")
    recommendations = client.get(f"/profiles/{profile_id}/recommendations", {"limit": 5})
    market = client.get("/market/top-skills", {"limit": 8})

    _log(args, "Generating truthful tailored resume")
    resume = client.post(
        "/resumes/generate",
        {
            "profile_id": profile_id,
            "internship_id": top_match["internship_id"],
            "max_claims": args.max_claims,
        },
    )

    summary = {
        "health": health,
        "profile_id": profile_id,
        "source_document_id": document["id"],
        "extraction_run_id": extraction["extraction_run_id"],
        "candidate_count": extraction["candidate_count"],
        "candidates_by_kind": extraction["candidates_by_kind"],
        "approved_claims_created": approved_count,
        "internships_created": len(internships),
        "profile_embeddings": len(profile_embeddings["embeddings"]),
        "embedding_rebuild": rebuild,
        "matches_ranked": [
            {
                "match_id": item["id"],
                "internship_id": item["internship_id"],
                "title": item["internship"]["title"],
                "company": item["internship"]["company_name"],
                "total_score": item["total_score"],
            }
            for item in demo_matches
        ],
        "top_match_id": top_match["id"],
        "top_match_title": top_match["internship"]["title"],
        "missing_skill_count_for_top_match": len(gaps["missing_skills"]),
        "covered_skill_count_for_top_match": len(gaps["covered_skills"]),
        "profile_gap_count": len(profile_gaps["items"]),
        "recommendations": [
            {"skill_name": item["skill_name"], "reason": item["reason"]}
            for item in recommendations["items"]
        ],
        "market_top_skills": [
            {"skill_name": item["skill_name"], "internship_count": item["internship_count"]}
            for item in market["items"]
        ],
        "generated_resume_id": resume["resume"]["id"],
        "generated_resume_html_path": resume["resume"]["rendered_html_path"],
        "generated_resume_claim_count": len(resume["claims"]),
        "safety": "Resume HTML was generated from approved claims only; no LLM-authored bullets.",
    }
    print(json.dumps(summary, indent=2))
    return 0


def _multipart_body(
    *,
    boundary: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
    content_type: str,
) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(f"{value}\r\n".encode("utf-8"))
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def _with_run_suffix(posting: dict[str, Any], run_id: str) -> dict[str, Any]:
    copied = dict(posting)
    copied["external_id"] = f"{posting['external_id']}-{run_id}"
    copied["source_url"] = f"{posting['source_url']}?demo_run={run_id}"
    copied["application_url"] = f"{posting['application_url']}?demo_run={run_id}"
    copied["metadata"] = {**copied.get("metadata", {}), "demo_run_id": run_id}
    return copied


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


def _log(args: argparse.Namespace, message: str) -> None:
    if not args.json:
        print(f"[CareerOS demo] {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
