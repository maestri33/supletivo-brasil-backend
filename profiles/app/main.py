     1|"""Entrypoint FastAPI — profiles."""
     2|
     3|from contextlib import asynccontextmanager
     4|
     5|from fastapi import FastAPI, Request
     6|from fastapi.middleware.cors import CORSMiddleware
     7|from fastapi.responses import JSONResponse
     8|
     9|from app.api.router import api_router
    10|from app.config import get_settings
    11|from app.db import close_db
    12|from app.exceptions import DomainError
    13|from app.utils.logging import configure_logging, get_logger
    14|from app.metrics import setup_metrics
    15|from slowapi import Limiter, _rate_limit_exceeded_handler
    16|from slowapi.errors import RateLimitExceeded
    17|from slowapi.util import get_remote_address
    18|
    19|settings = get_settings()
    20|configure_logging(settings.log_level)
    21|log = get_logger(__name__)
    22|
    23|
    24|@asynccontextmanager
    25|async def lifespan(app: FastAPI):
    26|    log.info("service.startup", service=settings.service_name, env=settings.env)
    27|    yield
    28|    await close_db()
    29|    log.info("service.shutdown")
    30|
    31|
    32|app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)
    33|
    34|# ── Rate limiting (slowapi) ─────────────────────────────────
    35|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    36|
    37|# ── SlowAPI middleware ──────────────────────────────────────
    38|app.state.limiter = limiter
    39|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    40|from slowapi.middleware import SlowAPIMiddleware
    41|app.add_middleware(SlowAPIMiddleware)
    42|
    43|
    44|app.add_middleware(
    45|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
    46|    allow_origins=settings.cors_origins.split(","),
    47|    allow_credentials=True,
    48|    allow_methods=["*"],
    49|    allow_headers=["*"],
    50|)
    51|
    52|
    53|@app.exception_handler(DomainError)
    54|async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    55|    return JSONResponse(
    56|        status_code=exc.status_code,
    57|        content={"code": exc.code, "message": exc.message},
    58|    )
    59|
    60|
    61|app.include_router(api_router)
    62|setup_metrics(app)
    63|
    64|