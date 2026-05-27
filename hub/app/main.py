     1|"""Entrypoint FastAPI — hub (polo).
     2|
     3|M2: health + read desmilitarizado.
     4|M3: write autenticado (staff only).
     5|"""
     6|
     7|import time
     8|from contextlib import asynccontextmanager
     9|
    10|import fastapi_structured_logging as fsl
    11|from fastapi import FastAPI, Request
    12|from fastapi.middleware.cors import CORSMiddleware
    13|from fastapi.responses import JSONResponse
    14|from sqlalchemy import text
    15|
    16|from app.api.hubs import authenticated, public
    17|from app.config import get_settings
    18|from app.db import async_session_maker, engine
    19|from app.exceptions import DomainError
    20|from app.metrics import setup_metrics
    21|from app.utils.logging import configure_logging
    22|
    23|
    24|def _cors_origins() -> list[str]:
    25|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    26|    import os as _os
    27|    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    28|    if env in ("development", "dev", "staging"):
    29|        return ["*"]
    30|    raw = _os.getenv("CORS_ORIGINS", "")
    31|    if raw:
    32|        return [o.strip() for o in raw.split(",") if o.strip()]
    33|    return []
    34|
    35|
    36|from slowapi import Limiter, _rate_limit_exceeded_handler
    37|from slowapi.errors import RateLimitExceeded
    38|from slowapi.util import get_remote_address
    39|
    40|settings = get_settings()
    41|_started_at = time.time()
    42|
    43|fsl.setup_logging(
    44|    json_logs=(settings.env != "dev"),
    45|    log_level=settings.log_level,
    46|)
    47|logger = fsl.get_logger()
    48|
    49|
    50|@asynccontextmanager
    51|async def lifespan(app: FastAPI):
    52|    logger.info("hub_starting", env=settings.env, schema=settings.database_schema)
    53|    yield
    54|    await engine.dispose()
    55|    logger.info("hub_stopped")
    56|
    57|
    58|configure_logging()
    59|
    60|app = FastAPI(
    61|    title=settings.service_name,
    62|    version="0.1.0",
    63|    lifespan=lifespan,
    64|)
    65|
    66|# ── Rate limiting (slowapi) ─────────────────────────────────
    67|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    68|
    69|# ── SlowAPI middleware ──────────────────────────────────────
    70|app.state.limiter = limiter
    71|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    72|from slowapi.middleware import SlowAPIMiddleware
    73|app.add_middleware(SlowAPIMiddleware)
    74|
    75|
    76|app.add_middleware(
    77|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
    78|    allow_origins=_cors_origins(),
    79|    allow_methods=["*"],
    80|    allow_headers=["*"],
    81|)
    82|
    83|# Routers: public (desmilitarizado) + authenticated (staff JWT)
    84|app.include_router(public)
    85|app.include_router(authenticated)
    86|setup_metrics(app)
    87|
    88|
    89|
    90|@app.exception_handler(DomainError)
    91|async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    92|    return JSONResponse(
    93|        status_code=exc.status_code,
    94|        content={"detail": exc.detail, "code": exc.code},
    95|    )
    96|
    97|
    98|# ── Structured access logging (healthcheck so loga se falhar) ──
    99|access_config = fsl.AccessLogConfig(
   100|    log_level="info",
   101|    exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
   102|    custom_fields={"service": settings.service_name, "env": settings.env},
   103|)
   104|app.add_middleware(fsl.AccessLogMiddleware, config=access_config)
   105|
   106|
   107|@app.get("/health")
   108|async def health():
   109|    return {"status": "ok", "service": settings.service_name}
   110|
   111|
   112|@app.get("/ready")
   113|async def ready():
   114|    try:
   115|        async with async_session_maker() as session:
   116|            await session.execute(text("SELECT 1"))
   117|        return {"status": "ok", "service": settings.service_name, "db": "ok"}
   118|    except Exception:
   119|        return {"status": "not_ready", "db": "unreachable"}
   120|
   121|
   122|@app.get("/status")
   123|async def status():
   124|    return {
   125|        "status": "ok",
   126|        "service": settings.service_name,
   127|        "version": app.version,
   128|        "environment": settings.env,
   129|        "uptime_seconds": int(time.time() - _started_at),
   130|    }
   131|