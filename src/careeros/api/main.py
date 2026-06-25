from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from careeros import __version__
from careeros.api.routes.applications import router as applications_router
from careeros.api.routes.documents import router as documents_router
from careeros.api.routes.embeddings import router as embeddings_router
from careeros.api.routes.extraction_runs import router as extraction_runs_router
from careeros.api.routes.fact_candidates import router as fact_candidates_router
from careeros.api.routes.gap_analysis import router as gap_analysis_router
from careeros.api.routes.health import router as health_router
from careeros.api.routes.internships import router as internships_router
from careeros.api.routes.matches import router as matches_router
from careeros.api.routes.profiles import router as profiles_router
from careeros.api.routes.resumes import router as resumes_router
from careeros.api.routes.skills import router as skills_router
from careeros.api.routes.sources import router as sources_router
from careeros.core.config import Settings, get_settings
from careeros.db.session import create_engine_from_settings, create_session_factory
from careeros.services.embedding_provider import build_embedding_provider
from careeros.services.normalization_seed import ensure_normalization_seed_data


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    engine = create_engine_from_settings(app_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        app_settings.storage_root.mkdir(parents=True, exist_ok=True)
        with session_factory() as session:
            ensure_normalization_seed_data(session)
        yield
        engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.embedding_provider = build_embedding_provider(app_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(profiles_router)
    app.include_router(documents_router)
    app.include_router(extraction_runs_router)
    app.include_router(fact_candidates_router)
    app.include_router(sources_router)
    app.include_router(internships_router)
    app.include_router(skills_router)
    app.include_router(embeddings_router)
    app.include_router(matches_router)
    app.include_router(gap_analysis_router)
    app.include_router(resumes_router)
    app.include_router(applications_router)
    return app
