"""
Agrega todos os routers do servico AI.
Rotas canonicas em /api/v1/ com aliases para paths legados.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.text import router as text_router
from app.api.image import router as image_router
from app.api.tts import router as tts_router
from app.api.json_endpoint import router as json_router
from app.api.ocr import router as ocr_router
from app.api.v1 import router as v1_router

router = APIRouter()

# ── Canonical /api/v1/* ───────────────────────────────────────────────

router.include_router(health_router, prefix="/api/v1")
router.include_router(text_router, prefix="/api/v1/text")
router.include_router(image_router, prefix="/api/v1/image")
router.include_router(tts_router, prefix="/api/v1/tts")
router.include_router(json_router, prefix="/api/v1/json")
router.include_router(ocr_router, prefix="/api/v1/ocr")
router.include_router(v1_router, prefix="/api/v1")

# ── Legacy aliases (backward compat) ──────────────────────────────────

router.include_router(health_router)                     # / , /health , /ready
router.include_router(text_router, prefix="/text")       # /text/
router.include_router(image_router, prefix="/image")     # /image/ , /image/vision
router.include_router(tts_router, prefix="/tts")         # /tts/
router.include_router(json_router, prefix="/json")       # /json/
router.include_router(ocr_router, prefix="/ocr")         # /ocr/
router.include_router(v1_router, prefix="/v1")           # /v1/text/chat , etc.
