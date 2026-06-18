from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from careeros import __version__
from careeros.api.routes.documents import router as documents_router
from careeros.api.routes.fact_candidates import router as fact_candidates_router
from careeros.api.routes.health import router as health_router
from careeros.api.routes.internships import router as internships_router
from careeros.api.routes.profiles import router as profiles_router
from careeros.api.routes.sources import router as sources_router
from careeros.core.config import Settings, get_settings
from careeros.db.session import create_engine_from_settings, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    engine = create_engine_from_settings(app_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        app_settings.storage_root.mkdir(parents=True, exist_ok=True)
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

    app.include_router(health_router)
    app.include_router(profiles_router)
    app.include_router(documents_router)
    app.include_router(fact_candidates_router)
    app.include_router(sources_router)
    app.include_router(internships_router)
    return app
