     1|"""Entrypoint FastAPI — lead service."""
     2|
     3|from contextlib import asynccontextmanager
     4|from datetime import datetime, timezone
     5|from pathlib import Path
     6|
     7|import fastapi_structured_logging
     8|from fastapi import FastAPI
     9|from fastapi.middleware.cors import CORSMiddleware
    10|from fastapi.staticfiles import StaticFiles
    11|from fastapi_structured_logging import AccessLogConfig, AccessLogMiddleware
    12|
    13|from app.config import settings
    14|from app.db import engine
    15|from app.api.public.auth import router as auth_router
    16|from app.api.demilitarized.webhooks import router as webhooks_router
    17|from app.api.demilitarized.leads import router as leads_crud_router
    18|from app.api.demilitarized.checkouts import router as checkouts_crud_router
    19|from app.api.health import router as health_router
    20|from app.metrics import setup_metrics
    21|from app.utils.logging import configure_logging
    22|from app.api.authenticated import (
    23|    captured_router,
    24|    waiting_router,
    25|    checkout_router,
    26|    completed_router,
    27|)
    28|
    29|fastapi_structured_logging.setup_logging(log_level=settings.LOG_LEVEL)
    30|logger = fastapi_structured_logging.get_logger()
    31|
    32|_started_at = datetime.now(timezone.utc)
    33|
    34|
    35|@asynccontextmanager
    36|async def lifespan(app: FastAPI):
    37|    logger.info("service.startup", service=settings.SERVICE_NAME, env=settings.ENVIRONMENT)
    38|    yield
    39|    await engine.dispose()
    40|    logger.info("service.shutdown", service=settings.SERVICE_NAME)
    41|
    42|
    43|configure_logging()
    44|
    45|app = FastAPI(
    46|    title=settings.SERVICE_NAME,
    47|    version=settings.APP_VERSION,
    48|    lifespan=lifespan,
    49|)
    50|
    51|app.add_middleware(
    52|    CORSMiddleware,
    53|    allow_origins=settings.CORS_ORIGINS,
    54|    allow_credentials=bool(settings.CORS_ORIGINS),
    55|    allow_methods=["*"],
    56|    allow_headers=["*"],
    57|)
    58|
    59|app.add_middleware(
    60|    AccessLogMiddleware,
    61|    config=AccessLogConfig(
    62|        exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
    63|    ),
    64|)
    65|
    66|app.include_router(auth_router)
    67|app.include_router(webhooks_router)
    68|app.include_router(leads_crud_router)
    69|app.include_router(checkouts_crud_router)
    70|app.include_router(captured_router)
    71|app.include_router(waiting_router)
    72|app.include_router(checkout_router)
    73|app.include_router(completed_router)
    74|app.include_router(health_router)
    75|setup_metrics(app)
    76|
    77|
    78|
    79|# ── Media estatico (QR Codes PIX + imagens) ─────────────────────────────────
    80|# Serve /api/v1/public/media/<...> a partir do volume lead_media. O prefixo
    81|# /api/v1/public/* casa com o matcher do Caddy listener PUBLICO (:8081), entao
    82|# imagens ficam acessiveis via Tailscale Funnel / dominio publico sem precisar
    83|# adicionar rota nova no proxy.
    84|#
    85|# Acesso: aberto publico (qualquer URL conhecida baixa o arquivo). Nao colocar
    86|# nada sensivel aqui — recibos, contratos, etc. devem ir por endpoint signed
    87|# ou JWT-gated em /api/v1/authenticated/*.
    88|_media_dir = Path(settings.MEDIA_DIR)
    89|(_media_dir / "qrcodes").mkdir(parents=True, exist_ok=True)
    90|(_media_dir / "images").mkdir(parents=True, exist_ok=True)
    91|app.mount("/api/v1/public/media", StaticFiles(directory=str(_media_dir)), name="media")
    92|
    93|
    94|# ── Health endpoints (root, sem prefixo) ────────────────────────────────────
    95|
    96|
    97|@app.get("/health")
    98|async def health():
    99|    return {"status": "ok", "service": settings.SERVICE_NAME}
   100|
   101|
   102|@app.get("/ready")
   103|async def ready():
   104|    return {"status": "ok", "service": settings.SERVICE_NAME}
   105|
   106|
   107|@app.get("/status")
   108|async def status():
   109|    return {"status": "ok", "service": settings.SERVICE_NAME}
   110|
   111|
   112|if __name__ == "__main__":
   113|    import uvicorn
   114|from slowapi import Limiter, _rate_limit_exceeded_handler
   115|from slowapi.errors import RateLimitExceeded
   116|from slowapi.util import get_remote_address
   117|
   118|# ── Rate limiting (slowapi) ─────────────────────────────────
   119|limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
   120|
   121|# ── SlowAPI middleware ──────────────────────────────────────
   122|app.state.limiter = limiter
   123|app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   124|from slowapi.middleware import SlowAPIMiddleware
   125|app.add_middleware(SlowAPIMiddleware)
   126|
   127|
   128|app.add_middleware(
   129|    CORSMiddleware,
# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
   130|    allow_origins=settings.CORS_ORIGINS,
   131|    allow_credentials=bool(settings.CORS_ORIGINS),
   132|    allow_methods=["*"],
   133|    allow_headers=["*"],
   134|)
   135|
   136|app.add_middleware(
   137|    AccessLogMiddleware,
   138|    config=AccessLogConfig(
   139|        exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
   140|    ),
   141|)
   142|
   143|app.include_router(auth_router)
   144|app.include_router(webhooks_router)
   145|app.include_router(leads_crud_router)
   146|app.include_router(checkouts_crud_router)
   147|app.include_router(captured_router)
   148|app.include_router(waiting_router)
   149|app.include_router(checkout_router)
   150|app.include_router(completed_router)
   151|app.include_router(health_router)
   152|setup_metrics(app)
   153|
   154|
   155|
   156|# ── Media estatico (QR Codes PIX + imagens) ─────────────────────────────────
   157|# Serve /api/v1/public/media/<...> a partir do volume lead_media. O prefixo
   158|# /api/v1/public/* casa com o matcher do Caddy listener PUBLICO (:8081), entao
   159|# imagens ficam acessiveis via Tailscale Funnel / dominio publico sem precisar
   160|# adicionar rota nova no proxy.
   161|#
   162|# Acesso: aberto publico (qualquer URL conhecida baixa o arquivo). Nao colocar
   163|# nada sensivel aqui — recibos, contratos, etc. devem ir por endpoint signed
   164|# ou JWT-gated em /api/v1/authenticated/*.
   165|_media_dir = Path(settings.MEDIA_DIR)
   166|(_media_dir / "qrcodes").mkdir(parents=True, exist_ok=True)
   167|(_media_dir / "images").mkdir(parents=True, exist_ok=True)
   168|app.mount("/api/v1/public/media", StaticFiles(directory=str(_media_dir)), name="media")
   169|
   170|
   171|# ── Health endpoints (root, sem prefixo) ────────────────────────────────────
   172|
   173|
   174|@app.get("/health")
   175|async def health():
   176|    return {"status": "ok", "service": settings.SERVICE_NAME}
   177|
   178|
   179|@app.get("/ready")
   180|async def ready():
   181|    return {"status": "ok", "service": settings.SERVICE_NAME}
   182|
   183|
   184|@app.get("/status")
   185|async def status():
   186|    return {"status": "ok", "service": settings.SERVICE_NAME}
   187|
   188|
   189|if __name__ == "__main__":
   190|    import uvicorn
   191|
   192|    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
   193|