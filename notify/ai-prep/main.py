"""
FastAPI entrypoint — servico AI (texto, imagem, TTS, JSON).
"""

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.config import get_settings

MEDIA_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "public", "media")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.join(MEDIA_ROOT, "image"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "audio"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "text"), exist_ok=True)
    yield


app = FastAPI(
    title="ai",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
