     1|"""Entrypoint do microsservico JWT — FastAPI + middlewares, zero banco."""
     2|
     3|from fastapi import FastAPI, Request
     4|from fastapi.middleware.cors import CORSMiddleware
     5|from fastapi.responses import JSONResponse
     6|
     7|from app.api.router import api_router
     8|from app.config import get_settings
     9|from app.exceptions import DomainError
    10|from app.stats import get_stats
    11|from app.utils.logging import RequestLoggingMiddleware, configure_logging, get_logger
    12|from app.metrics import setup_metrics
    13|
    14|
    15|def _cors_origins() -> list[str]:
    16|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    17|    import os as _os
    18|from slowapi import Limiter, _rate_limit_exceeded_handler
    19|from slowapi.errors import RateLimitExceeded
    20|from slowapi.util import get_remote_address
    21|    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    22|    if env in ("development", "dev", "staging"):
    23|        return ["*"]
    24|    raw = _os.getenv("CORS_ORIGINS", "")
    25|    if raw:
    26|        return [o.strip() for o in raw.split(",") if o.strip()]
    27|    return []
    28|
    29|
    30|# -- Boot --
    31|settings = get_settings()
    32|configure_logging(settings.log_level)
    33|log = get_logger(__name__)
    34|
    35|log.info("service.startup", service=settings.service_name, env=settings.env)
    36|
    37|
    38|# -- App --
    39|app = FastAPI(title=settings.service_name, version="1.0.0")
    40|
    41|# ── Rate limiting (slowapi) ─────────────────────────────────
    42|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    43|
    44|# ── SlowAPI middleware ──────────────────────────────────────
    45|app.state.limiter = limiter
    46|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    47|from slowapi.middleware import SlowAPIMiddleware
    48|app.add_middleware(SlowAPIMiddleware)
    49|
    50|
    51|app.add_middleware(RequestLoggingMiddleware)
    52|_origins = _cors_origins()
    53|app.add_middleware(
    54|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
    55|    allow_origins=_origins,
    56|    allow_credentials=bool(_origins and _origins != ["*"]),
    57|    allow_methods=["*"],
    58|    allow_headers=["*"],
    59|)
    60|
    61|
    62|@app.exception_handler(DomainError)
    63|async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    64|    get_stats().inc_error()
    65|    return JSONResponse(
    66|        status_code=exc.status_code,
    67|        content={"code": exc.code, "message": exc.message},
    68|    )
    69|
    70|
    71|app.include_router(api_router)
    72|setup_metrics(app)
    73|
    74|