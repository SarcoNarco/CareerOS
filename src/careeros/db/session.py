from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from careeros.core.config import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    connect_args: dict[str, bool] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

