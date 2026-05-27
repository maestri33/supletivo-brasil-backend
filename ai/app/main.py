"""
FastAPI entrypoint — servico AI (texto, imagem, TTS, JSON).
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.utils.media import MEDIA_ROOT
from app.metrics import setup_metrics
from app.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.join(MEDIA_ROOT, "image"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "audio"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "text"), exist_ok=True)
    yield


configure_logging()

app = FastAPI(
    title="ai",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
setup_metrics(app)

app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
