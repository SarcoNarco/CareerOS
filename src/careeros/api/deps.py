from collections.abc import Generator
from secrets import compare_digest

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from careeros.core.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_db_session(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    expected_token = settings.api_token.get_secret_value()
    if x_api_token is None or not compare_digest(x_api_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )
