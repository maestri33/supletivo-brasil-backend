"""Agrega os routers da API do training (cada um com seu proprio prefixo)."""

from fastapi import APIRouter

from app.api.demilitarized.materials import router as materials_router
from app.api.health import router as health_router

api_router = APIRouter()

# Desmilitarizadas (uso interno da plataforma)
api_router.include_router(materials_router)

# Health
api_router.include_router(health_router)
