"""Aggregator router — commissions service."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.commissions import router as commissions_router
from app.api.batches import router as batches_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(commissions_router)
api_router.include_router(batches_router)
