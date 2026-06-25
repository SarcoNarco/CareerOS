#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"


@dataclass(slots=True)
class ValidationStep:
    name: str
    command: list[str]
    required: bool = True
    cwd: Path = ROOT_DIR


@dataclass(slots=True)
class ValidationResult:
    step: ValidationStep
    returncode: int
    output: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CareerOS V1 local validation checks.")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--live-sources", action="store_true")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    steps = build_validation_steps(
        skip_frontend=args.skip_frontend,
        live_sources=args.live_sources,
        quick=args.quick,
    )
    results = [run_step(step) for step in steps]
    _print_results(results)
    return 1 if any(not result.passed and result.step.required for result in results) else 0


def build_validation_steps(
    *,
    skip_frontend: bool,
    live_sources: bool,
    quick: bool,
) -> list[ValidationStep]:
    python = _python_bin()
    env = _validation_env_prefix()
    steps = [
        ValidationStep("demo script help", [python, "scripts/run_v1_demo.py", "--help"]),
        ValidationStep("source sync help", [python, "scripts/sync_source.py", "--help"]),
        ValidationStep("job discovery help", [python, "scripts/run_job_discovery.py", "--help"]),
        ValidationStep("application list help", [python, "scripts/list_applications.py", "--help"]),
        ValidationStep("embedding smoke check", [python, "scripts/check_embeddings.py"]),
        ValidationStep("matching quality evaluation", [python, "scripts/evaluate_matching_quality.py"]),
    ]
    if not quick:
        steps.insert(0, ValidationStep("backend test suite", [python, "-m", "pytest"]))
        steps.insert(1, ValidationStep("alembic upgrade head", [python, "-m", "alembic", "upgrade", "head"]))
    if not skip_frontend and FRONTEND_DIR.exists():
        steps.append(ValidationStep("frontend build", ["npm", "run", "build"], cwd=FRONTEND_DIR))
    if live_sources:
        steps.append(
            ValidationStep(
                "live source help check",
                [python, "scripts/check_sources.py", "--help"],
            )
        )

    for step in steps:
        if step.command[0] == python:
            step.command.insert(0, env)
    return steps


def run_step(step: ValidationStep) -> ValidationResult:
    command = step.command
    shell = False
    if command and command[0].startswith("PYTHONPATH="):
        command = [" ".join(command)]
        shell = True
    completed = subprocess.run(
        command,
        cwd=step.cwd,
        shell=shell,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return ValidationResult(step=step, returncode=completed.returncode, output=output)


def _print_results(results: list[ValidationResult]) -> None:
    print("CareerOS V1 validation")
    print()
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        required = "required" if result.step.required else "optional"
        print(f"- {status}: {result.step.name} ({required})")
        print(f"  command: {_display_command(result.step)}")
        if not result.passed and result.output:
            print(f"  output: {result.output[:800]}")


def _display_command(step: ValidationStep) -> str:
    return " ".join(step.command)


def _python_bin() -> str:
    candidate = ROOT_DIR / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def _validation_env_prefix() -> str:
    existing = os.environ.get("PYTHONPATH")
    existing_parts = [part for part in (existing or "").split(":") if part]
    value = ":".join(["src", *[part for part in existing_parts if part != "src"]])
    return f"PYTHONPATH={value}"


if __name__ == "__main__":
    raise SystemExit(main())
