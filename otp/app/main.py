     1|"""
     2|FastAPI entrypoint.
     3|
     4|Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
     5|"""
     6|
     7|import asyncio
     8|from collections.abc import AsyncIterator
     9|from contextlib import asynccontextmanager
    10|
    11|import httpx
    12|from fastapi import FastAPI, Request
    13|from fastapi.middleware.cors import CORSMiddleware
    14|from fastapi.responses import JSONResponse
    15|
    16|from app.api.router import api_router
    17|from app.api.status import router as status_router
    18|from app.config import get_settings
    19|from app.db import close_db
    20|from app.exceptions import DomainError, RateLimitExceeded
    21|from app.services.cleanup import cleanup_loop
    22|from app.services.queue import queue_loop
    23|from app.utils.logging import configure_logging, get_logger
    24|from app.metrics import setup_metrics
    25|from slowapi import Limiter, _rate_limit_exceeded_handler
    26|from slowapi.errors import RateLimitExceeded
    27|from slowapi.util import get_remote_address
    28|
    29|
    30|def _cors_origins() -> list[str]:
    31|    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    32|    import os as _os
    33|    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    34|    if env in ("development", "dev", "staging"):
    35|        return ["*"]
    36|    raw = _os.getenv("CORS_ORIGINS", "")
    37|    if raw:
    38|        return [o.strip() for o in raw.split(",") if o.strip()]
    39|    return []
    40|
    41|
    42|settings = get_settings()
    43|configure_logging(settings.log_level, settings.env)
    44|log = get_logger(__name__)
    45|
    46|
    47|@asynccontextmanager
    48|async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    49|    log.info("service.startup", service=settings.service_name, env=settings.env)
    50|
    51|    stop_event = asyncio.Event()
    52|    http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    53|    queue_task = asyncio.create_task(queue_loop(http, stop_event))
    54|    cleanup_task = asyncio.create_task(cleanup_loop(stop_event))
    55|
    56|    try:
    57|        yield
    58|    finally:
    59|        stop_event.set()
    60|        await queue_task
    61|        await cleanup_task
    62|        await http.aclose()
    63|        await close_db()
    64|        log.info("service.shutdown")
    65|
    66|
    67|app = FastAPI(
    68|    title=settings.service_name,
    69|    version="0.2.0",
    70|    lifespan=lifespan,
    71|    description="""
    72|Microsserviço **OTP** — geração e validação de códigos de autenticação descartáveis.
    73|
    74|## Funcionalidades
    75|
    76|- Gera código OTP numérico e envia via serviço externo **notify**.
    77|- Valida código OTP contra hash SHA256 com TTL configurável.
    78|- Rate limit dedicado por `external_id` (janela curta + janela horária).
    79|- Cleanup automático de logs antigos como task de fundo no lifespan.
    80|- Configuração via variáveis de ambiente (`.env`).
    81|- Logs estruturados em JSON de todas as operações.
    82|- `GET /status` — métricas do serviço (uptime, conexões, latência, falhas).
    83|
    84|## Integração
    85|
    86|Envia mensagens para o serviço **notify** (`10.10.10.157/api/v1`).
    87|O contacto deve existir previamente no notify.
    88|""",
    89|)
    90|
    91|# ── Rate limiting (slowapi) ─────────────────────────────────
    92|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    93|
    94|# ── SlowAPI middleware ──────────────────────────────────────
    95|app.state.limiter = limiter
    96|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    97|from slowapi.middleware import SlowAPIMiddleware
    98|app.add_middleware(SlowAPIMiddleware)
    99|
   100|
   101|# DMZ: CORS origins driven by env. Dev/staging = *, prod = CORS_ORIGINS (COD-18 P0.2).
   102|_origins = _cors_origins()
   103|app.add_middleware(
   104|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
   105|    allow_origins=_origins,
   106|    allow_credentials=bool(_origins and _origins != ["*"]),
   107|    allow_methods=["*"],
   108|    allow_headers=["*"],
   109|)
   110|
   111|
   112|@app.exception_handler(RateLimitExceeded)
   113|async def _handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
   114|    """429 com header Retry-After (segundos)."""
   115|    headers = {}
   116|    if exc.retry_after_s > 0:
   117|        headers["Retry-After"] = str(exc.retry_after_s)
   118|    return JSONResponse(
   119|        status_code=exc.status_code,
   120|        content={
   121|            "code": exc.code,
   122|            "message": exc.message,
   123|            "retry_after_s": exc.retry_after_s,
   124|        },
   125|        headers=headers,
   126|    )
   127|
   128|
   129|@app.exception_handler(DomainError)
   130|async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
   131|    """Convert domain exceptions to standardized HTTP responses."""
   132|    return JSONResponse(
   133|        status_code=exc.status_code,
   134|        content={"code": exc.code, "message": exc.message},
   135|    )
   136|
   137|
   138|app.include_router(status_router)
   139|app.include_router(api_router)
   140|setup_metrics(app)
   141|
   142|