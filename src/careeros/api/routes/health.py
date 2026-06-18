from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, get_settings
from careeros.core.config import Settings
from careeros.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        database="ok",
    )

