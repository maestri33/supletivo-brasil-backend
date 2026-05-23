"""SQLAlchemy engine + session helpers (sync, Postgres)."""

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

_metadata = MetaData(schema=_settings.database_schema)
Base = declarative_base(metadata=_metadata)


def init_db() -> None:
    """No-op — schema é gerenciado por Alembic."""
    return None


def get_session():
    """FastAPI dependency — yields a session and closes it."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
