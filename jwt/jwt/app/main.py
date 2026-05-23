"""Entrypoint do microsservico JWT — FastAPI + middlewares, zero banco."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.exceptions import DomainError
from app.stats import get_stats
from app.utils.logging import RequestLoggingMiddleware, configure_logging, get_logger

# -- Boot --
settings = get_settings()
configure_logging(settings.log_level)
log = get_logger(__name__)

log.info("service.startup", service=settings.service_name, env=settings.env)


# -- App --
app = FastAPI(title=settings.service_name, version="1.0.0")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    get_stats().inc_error()
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


app.include_router(api_router)
