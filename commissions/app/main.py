"""Entrypoint FastAPI — commissions (Parte B — Sprint futuro)."""

from fastapi import FastAPI
from app.api.health import router as health_router
from app.config import get_settings
from app.metrics import setup_metrics
from app.utils.logging import configure_logging

settings = get_settings()

configure_logging()

app = FastAPI(title=settings.service_name, version=settings.version)
app.include_router(health_router)
setup_metrics(app)



if __name__ == "__main__":
    import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

app.include_router(health_router)
setup_metrics(app)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
