"""Router agregador — todo recurso adiciona seu router aqui."""

from fastapi import APIRouter

from app.api import addresses, entity_addresses, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(addresses.router, tags=["addresses"])
api_router.include_router(entity_addresses.router, tags=["entities"])
