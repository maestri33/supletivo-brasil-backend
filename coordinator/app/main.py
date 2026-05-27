"""Entrypoint FastAPI — coordinator service.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 8015
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.metrics import setup_metrics
from app.utils.logging import configure_logging, get_logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

settings = get_settings()
configure_logging(level=settings.log_level)
logger = get_logger("coordinator")

app = FastAPI(title=settings.service_name, version=settings.version)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


# ── Error handlers ──────────────────────────────────────────
class _DomainError(Exception):
    """Erro de dominio com status HTTP."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@app.exception_handler(_DomainError)
async def _handle_domain_error(request: Request, exc: _DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# ── Routers ─────────────────────────────────────────────────
app.include_router(api_router)
setup_metrics(app)


# ── Health / diagnostics ────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": settings.service_name}


@app.get("/status")
async def status():

    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
