"""Entrypoint FastAPI — commissions (Parte B — Sprint futuro)."""

from fastapi import FastAPI
from app.api.health import router as health_router
from app.config import get_settings
from app.metrics import setup_metrics
from app.utils.logging import configure_logging

settings = get_settings()

configure_logging()

app = FastAPI(title=settings.service_name, version=settings.version)
app.include_router(health_router)
setup_metrics(app)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
