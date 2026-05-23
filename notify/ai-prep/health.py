"""
GET /health, GET /ready
"""

import time
from fastapi import APIRouter

router = APIRouter(tags=["health"])

_started_at = time.time()


@router.get("/")
async def root():
    return {
        "service": "ai",
        "version": "1.0.0",
        "status": "ok",
        "uptime_seconds": round(time.time() - _started_at, 1),
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "text": "/text/",
            "image": "/image/",
            "tts": "/tts/",
            "json": "/json/",
            "docs": "/docs",
        },
    }


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ai"}


@router.get("/ready")
async def ready():
    return {"status": "ok"}
