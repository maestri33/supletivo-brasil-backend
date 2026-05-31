"""Agrega todos os routers da API v1 e expoe o webhook na raiz."""

from fastapi import APIRouter

from .demilitarized.charge import router as charge_router
from .demilitarized.config import router as config_router
from .demilitarized.payment import router as payment_router
from .demilitarized.pixkey import router as pixkey_router
from .health import router as health_router
from .public.webhook import router as webhook_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(config_router)
api_router.include_router(payment_router)
api_router.include_router(pixkey_router)
api_router.include_router(charge_router)

# Webhook e security-validator ficam na raiz (Asaas chama URLs fixas)
root_router = APIRouter()
root_router.include_router(health_router)
root_router.include_router(webhook_router)
