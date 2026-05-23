from fastapi import APIRouter
from app.api import health, documents

router = APIRouter()
router.include_router(health.router)
router.include_router(documents.router)
