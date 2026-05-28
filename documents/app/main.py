"""FastAPI application — documents service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import close_db
from app.api.router import router
from app.metrics import setup_metrics
from app.utils.logging import configure_logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


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

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


app.include_router(router)
setup_metrics(app)

app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
