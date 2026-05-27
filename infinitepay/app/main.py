     1|"""Entrypoint FastAPI.
     2|
     3|Roda em: uvicorn app.main:app --host 0.0.0.0 --port 8000
     4|"""
     5|
     6|import asyncio
     7|import os
     8|from collections.abc import AsyncIterator
     9|from contextlib import asynccontextmanager
    10|
    11|from fastapi import FastAPI
    12|from fastapi.middleware.cors import CORSMiddleware
    13|from fastapi.responses import JSONResponse
    14|from slowapi import Limiter, _rate_limit_exceeded_handler
    15|from slowapi.errors import RateLimitExceeded
    16|from slowapi.util import get_remote_address
    17|
    18|from app.api.health import router as health_router
    19|from app.api.integration_health import router as integration_health_router
    20|from app.api.router import router as api_router
    21|from app.config import get_settings
    22|from app.db import close_db
    23|from app.exceptions import DomainError
    24|from app.metrics import setup_metrics
    25|from app.utils.logging import configure_logging, log_event
    26|from app.workers import outbound_queue
    27|
    28|
    29|@asynccontextmanager
    30|async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    31|    log_event("service.startup")
    32|    stop = asyncio.Event()
    33|    worker_task: asyncio.Task | None = None
    34|    if get_settings().run_inline_worker:
    35|        worker_task = asyncio.create_task(outbound_queue.run_worker_loop(stop))
    36|    try:
    37|        yield
    38|    finally:
    39|        stop.set()
    40|        if worker_task is not None:
    41|            worker_task.cancel()
    42|            try:
    43|                await worker_task
    44|            except asyncio.CancelledError:
    45|                pass
    46|        log_event("service.shutdown")
    47|        await close_db()
    48|
    49|
    50|def _cors_origins() -> list[str]:
    51|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    52|    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    53|    if env in ("development", "dev", "staging"):
    54|        return ["*"]
    55|    raw = os.getenv("CORS_ORIGINS", "")
    56|    if raw:
    57|        return [o.strip() for o in raw.split(",") if o.strip()]
    58|    return []
    59|
    60|
    61|def create_app() -> FastAPI:
    62|    configure_logging()
    63|
    64|    tags_metadata = [
    65|        {"name": "health", "description": "Health check e readiness probe."},
    66|        {
    67|            "name": "checkout",
    68|            "description": "Criacao, listagem e consulta de links de pagamento InfinitePay.",
    69|        },
    70|        {
    71|            "name": "webhook",
    72|            "description": "Recebimento de webhooks server-to-server da InfinitePay.",
    73|        },
    74|    ]
    75|
    76|    app = FastAPI(
    77|        title="infinitepay API",
    78|        version="1.0.0",
    79|        description="Integracao com a API de checkout da InfinitePay.",
    80|        contact={"name": "InfinitePay Team"},
    81|        license_info={"name": "MIT"},
    82|        openapi_tags=tags_metadata,
    83|        summary="Cria checkouts InfinitePay, recebe webhooks e reenvia eventos internos.",
    84|        lifespan=lifespan,
    85|    )
    86|
    87|    # ── Rate limiting (slowapi) ─────────────────────────────────
    88|    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    89|
    90|    # ── SlowAPI middleware ──────────────────────────────────────
    91|    app.state.limiter = limiter
    92|    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    93|    from slowapi.middleware import SlowAPIMiddleware
    94|    app.add_middleware(SlowAPIMiddleware)
    95|
    96|
    97|    _origins = _cors_origins()
    98|    app.add_middleware(
    99|        CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
   100|        allow_origins=_origins,
   101|        allow_credentials=bool(_origins and _origins != ["*"]),
   102|        allow_methods=["*"],
   103|        allow_headers=["*"],
   104|    )
   105|
   106|    @app.exception_handler(DomainError)
   107|    async def _domain_err(_req, exc: DomainError):
   108|        return JSONResponse(status_code=exc.code, content={"detail": str(exc), **exc.extra})
   109|
   110|    app.include_router(health_router, tags=["health"])
   111|    app.include_router(integration_health_router, tags=["health"])
   112|    app.include_router(api_router)
   113|    setup_metrics(app)
   114|    return app
   115|
   116|
   117|app = create_app()
   118|