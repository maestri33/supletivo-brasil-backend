"""Aggregator router — coordinator service."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.coordinator import router as coordinator_router
from app.api.training import router as training_router
from app.api.fees import router as fees_router
from app.api.exams import router as exams_router
from app.api.documents import router as documents_router
from app.api.diplomas import router as diplomas_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(coordinator_router, prefix="/api/v1")
api_router.include_router(training_router, prefix="/api/v1")
api_router.include_router(fees_router, prefix="/api/v1")
api_router.include_router(exams_router, prefix="/api/v1")
api_router.include_router(documents_router, prefix="/api/v1")
api_router.include_router(diplomas_router, prefix="/api/v1")
