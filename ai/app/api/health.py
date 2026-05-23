"""
GET /, /health, /ready
"""

import time

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])

_started_at = time.time()


def _integration_status() -> dict:
    settings = get_settings()
    return {
        "deepseek": {
            "configured": bool(settings.deepseek_api_key),
            "model": settings.deepseek_default_model,
        },
        "gemini": {
            "configured": bool(settings.gemini_api_key),
            "image_model": settings.gemini_image_model,
            "vision_model": settings.gemini_vision_model,
        },
        "elevenlabs": {
            "configured": bool(settings.elevenlabs_api_key),
            "voice_id": settings.elevenlabs_voice_id,
            "model_id": settings.elevenlabs_model_id,
        },
    }


@router.get("/")
async def root():
    return {
        "service": "ai",
        "version": "1.0.0",
        "status": "ok",
        "uptime_seconds": round(time.time() - _started_at, 1),
        "integrations": _integration_status(),
        "endpoints": {
            "health": "/api/v1/health",
            "ready": "/api/v1/ready",
            "text": "/api/v1/text/",
            "json": "/api/v1/json/",
            "image": "/api/v1/image/",
            "image_vision": "/api/v1/image/vision",
            "tts": "/api/v1/tts/",
            "chat": "/api/v1/text/chat",
            "summarize": "/api/v1/text/summarize",
            "extract": "/api/v1/text/extract",
            "docs": "/docs",
        },
        "legacy_aliases": {
            "/": "/api/v1/",
            "/health": "/api/v1/health",
            "/text/": "/api/v1/text/",
            "/json/": "/api/v1/json/",
            "/image/": "/api/v1/image/",
            "/tts/": "/api/v1/tts/",
            "/v1/": "/api/v1/",
        },
    }


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ai"}


@router.get("/ready")
async def ready():
    settings = get_settings()
    integrations_ok = all([
        bool(settings.deepseek_api_key),
        bool(settings.gemini_api_key),
        bool(settings.elevenlabs_api_key),
    ])
    status = "ok" if integrations_ok else "degraded"
    return {"status": status, "integrations": _integration_status()}


@router.get("/status")
async def status():
    return {
        "status": "ok",
        "service": "ai",
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - _started_at),
        "integrations": _integration_status(),
    }
