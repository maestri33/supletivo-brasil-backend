"""FastAPI application — documents service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import close_db
from app.api.router import router
from app.metrics import setup_metrics
from app.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: engine e criado ao iniciar e disposto ao parar."""
    yield
    await close_db()


settings = get_settings()

configure_logging()

app = FastAPI(
    title=settings.service_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(router)
setup_metrics(app)

app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
