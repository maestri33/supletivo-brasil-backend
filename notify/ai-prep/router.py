"""
Agrega todos os routers do servico AI.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.text import router as text_router
from app.api.image import router as image_router
from app.api.tts import router as tts_router
from app.api.json_endpoint import router as json_router

router = APIRouter()
router.include_router(health_router)
router.include_router(text_router)
router.include_router(image_router)
router.include_router(tts_router)
router.include_router(json_router)
