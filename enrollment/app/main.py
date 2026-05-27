     1|"""Entrypoint FastAPI — enrollment (stub auditivo)."""
     2|
     3|import time
     4|from contextlib import asynccontextmanager
     5|
     6|import fastapi_structured_logging as fsl
     7|from fastapi import FastAPI, Request
     8|from fastapi.middleware.cors import CORSMiddleware
     9|from fastapi.responses import JSONResponse
    10|from sqlalchemy import text
    11|
    12|from app.api.router import api_router
    13|from app.config import get_settings
    14|from app.db import async_session_maker, engine
    15|from app.exceptions import DomainError
    16|from app.metrics import setup_metrics
    17|from app.utils.logging import configure_logging
    18|
    19|
    20|def _cors_origins() -> list[str]:
    21|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    22|    import os as _os
    23|    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    24|    if env in ("development", "dev", "staging"):
    25|        return ["*"]
    26|    raw = _os.getenv("CORS_ORIGINS", "")
    27|    if raw:
    28|        return [o.strip() for o in raw.split(",") if o.strip()]
    29|    return []
    30|
    31|
    32|from slowapi import Limiter, _rate_limit_exceeded_handler
    33|from slowapi.errors import RateLimitExceeded
    34|from slowapi.util import get_remote_address
    35|
    36|settings = get_settings()
    37|_started_at = time.time()
    38|
    39|fsl.setup_logging(
    40|    json_logs=(settings.env != "dev"),
    41|    log_level=settings.log_level,
    42|)
    43|logger = fsl.get_logger()
    44|
    45|
    46|@asynccontextmanager
    47|async def lifespan(app: FastAPI):
    48|    logger.info("enrollment_starting", env=settings.env, schema=settings.database_schema)
    49|    yield
    50|    await engine.dispose()
    51|    logger.info("enrollment_stopped")
    52|
    53|
    54|configure_logging()
    55|
    56|app = FastAPI(
    57|    title=settings.service_name,
    58|    version="0.1.0",
    59|    lifespan=lifespan,
    60|)
    61|
    62|# ── Rate limiting (slowapi) ─────────────────────────────────
    63|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    64|
    65|# ── SlowAPI middleware ──────────────────────────────────────
    66|app.state.limiter = limiter
    67|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    68|from slowapi.middleware import SlowAPIMiddleware
    69|app.add_middleware(SlowAPIMiddleware)
    70|
    71|
    72|app.add_middleware(
    73|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
    74|    allow_origins=_cors_origins(),
    75|    allow_methods=["*"],
    76|    allow_headers=["*"],
    77|)
    78|
    79|app.include_router(api_router)
    80|setup_metrics(app)
    81|
    82|
    83|
    84|@app.exception_handler(DomainError)
    85|async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    86|    return JSONResponse(
    87|        status_code=exc.status_code,
    88|        content={"detail": exc.detail, "code": exc.code},
    89|    )
    90|
    91|
    92|# ── Structured access logging (porta do local; healthcheck só loga se falhar) ──
    93|access_config = fsl.AccessLogConfig(
    94|    log_level="info",
    95|    exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
    96|    custom_fields={"service": settings.service_name, "env": settings.env},
    97|)
    98|app.add_middleware(fsl.AccessLogMiddleware, config=access_config)
    99|
   100|
   101|@app.get("/health")
   102|async def health():
   103|    return {"status": "ok", "service": settings.service_name}
   104|
   105|
   106|@app.get("/ready")
   107|async def ready():
   108|    try:
   109|        async with async_session_maker() as session:
   110|            await session.execute(text("SELECT 1"))
   111|        return {"status": "ok", "service": settings.service_name, "db": "ok"}
   112|    except Exception:
   113|        return {"status": "not_ready", "db": "unreachable"}
   114|
   115|
   116|@app.get("/status")
   117|async def status():
   118|    return {
   119|        "status": "ok",
   120|        "service": settings.service_name,
   121|        "version": app.version,
   122|        "environment": settings.env,
   123|        "uptime_seconds": int(time.time() - _started_at),
   124|    }
   125|