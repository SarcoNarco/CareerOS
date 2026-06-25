from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from careeros.api.main import create_app
from careeros.core.config import Settings
from careeros.db.base import Base
from careeros.db.models import (  # noqa: F401
    ApprovedClaim,
    ApplicationRecord,
    EmbeddingRebuildQueue,
    EntityEmbedding,
    ExtractionRun,
    FactCandidate,
    FactEvidenceSpan,
    GeneratedResume,
    GeneratedResumeClaim,
    IngestionRun,
    Internship,
    InternshipMatch,
    InternshipSkillRequirement,
    InternshipSource,
    MatchRun,
    NormalizedLocation,
    NormalizedTitle,
    Profile,
    RawPosting,
    ResumeTemplate,
    SkillAlias,
    SkillCatalog,
    SkillGapItem,
    SourceDocument,
    SourcePolicy,
    TitleAlias,
    User,
    VerificationEvent,
)


@pytest.fixture()
def app_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        api_token="test-token",
        storage_root=tmp_path / "incoming",
        app_host="127.0.0.1",
        app_port=8001,
        embedding_provider="deterministic",
        embedding_dimension=64,
    )


@pytest.fixture()
def app(app_settings: Settings):
    application = create_app(app_settings)
    Base.metadata.create_all(bind=application.state.engine)
    return application


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(app_settings: Settings) -> dict[str, str]:
    return {"X-API-Token": app_settings.api_token.get_secret_value()}


@pytest.fixture()
def db_session(app) -> Generator[Session, None, None]:
    session: Session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
