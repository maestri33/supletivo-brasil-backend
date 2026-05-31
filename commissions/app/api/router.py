"""Aggregator router — commissions service."""

from fastapi import APIRouter

from app.api.demilitarized.batches import router as batches_router
from app.api.demilitarized.commissions import router as commissions_router
from app.api.demilitarized.webhook import router as webhook_router
from app.api.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(commissions_router)
api_router.include_router(batches_router)
api_router.include_router(webhook_router)
