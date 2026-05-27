     1|"""Entrypoint FastAPI — notify (SQLAlchemy 2)."""
     2|
     3|import os
     4|import time
     5|from collections.abc import AsyncIterator
     6|from contextlib import asynccontextmanager
     7|
     8|from fastapi import FastAPI, Request
     9|from fastapi.middleware.cors import CORSMiddleware
    10|from fastapi.responses import JSONResponse
    11|from fastapi.staticfiles import StaticFiles
    12|from sqlalchemy import text
    13|
    14|from app.api.router import api_router
    15|from app.config import get_settings
    16|from app.db import async_session_maker, close_db
    17|from app.exceptions import DomainError
    18|from app.services import metrics_service, template_service
    19|from app.utils.logging import configure_logging, get_logger
    20|from app.metrics import setup_metrics
    21|from slowapi import Limiter, _rate_limit_exceeded_handler
    22|from slowapi.errors import RateLimitExceeded
    23|from slowapi.util import get_remote_address
    24|
    25|
    26|def _cors_origins() -> list[str]:
    27|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    28|    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    29|    if env in ("development", "dev", "staging"):
    30|        return ["*"]
    31|    raw = os.getenv("CORS_ORIGINS", "")
    32|    if raw:
    33|        return [o.strip() for o in raw.split(",") if o.strip()]
    34|    return []
    35|
    36|
    37|settings = get_settings()
    38|configure_logging(settings.log_level, json_mode=settings.env != "dev")
    39|log = get_logger(__name__)
    40|
    41|_started_at = time.time()
    42|
    43|
    44|@asynccontextmanager
    45|async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    46|    log.info("service.startup", service=settings.service_name, env=settings.env)
    47|    try:
    48|        await template_service.bootstrap_from_disk_if_needed()
    49|    except Exception as exc:  # noqa: BLE001 — bootstrap nao pode bloquear startup
    50|        log.warning("template.bootstrap_failed", error=str(exc))
    51|    try:
    52|        yield
    53|    finally:
    54|        await close_db()
    55|        log.info("service.shutdown")
    56|
    57|
    58|app = FastAPI(
    59|    title=settings.service_name,
    60|    version="0.5.0",
    61|    lifespan=lifespan,
    62|)
    63|
    64|# ── Rate limiting (slowapi) ─────────────────────────────────
    65|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    66|
    67|# ── SlowAPI middleware ──────────────────────────────────────
    68|app.state.limiter = limiter
    69|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    70|from slowapi.middleware import SlowAPIMiddleware
    71|app.add_middleware(SlowAPIMiddleware)
    72|
    73|
    74|_origins = _cors_origins()
    75|app.add_middleware(
    76|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
    77|    allow_origins=_origins,
    78|    allow_credentials=bool(_origins and _origins != ["*"]),
    79|    allow_methods=["*"],
    80|    allow_headers=["*"],
    81|)
    82|
    83|
    84|@app.exception_handler(DomainError)
    85|async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    86|    return JSONResponse(
    87|        status_code=exc.status_code,
    88|        content={"code": exc.code, "message": exc.message},
    89|    )
    90|
    91|
    92|# ── Convenção v7m: /health, /ready, /status no root ───────────────────────
    93|
    94|
    95|@app.get("/health")
    96|async def health() -> dict:
    97|    return {"status": "ok", "service": settings.service_name}
    98|
    99|
   100|@app.get("/ready")
   101|async def ready() -> dict:
   102|    try:
   103|        async with async_session_maker() as session:
   104|            await session.execute(text("SELECT 1"))
   105|        return {"status": "ok", "service": settings.service_name, "db": "ok"}
   106|    except Exception:
   107|        return {"status": "not_ready", "db": "unreachable"}
   108|
   109|
   110|@app.get("/status")
   111|async def status() -> dict:
   112|    """Status + uptime + metricas agregadas (24h por padrao).
   113|
   114|    Use `window_hours` query param para outra janela:
   115|      GET /status?window_hours=1
   116|    """
   117|    return {
   118|        "status": "ok",
   119|        "service": settings.service_name,
   120|        "version": app.version,
   121|        "environment": settings.env,
   122|        "uptime_seconds": int(time.time() - _started_at),
   123|        "metrics": await metrics_service.status_snapshot(window_hours=24),
   124|    }
   125|
   126|
   127|# ── Routers e media ───────────────────────────────────────────────────────
   128|
   129|
   130|app.include_router(api_router, prefix="/api/v1")
   131|setup_metrics(app)
   132|
   133|
   134|os.makedirs("media", exist_ok=True)
   135|app.mount("/media", StaticFiles(directory="media"), name="media")
   136|