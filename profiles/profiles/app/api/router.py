"""Router agregador — todo recurso adiciona seu router aqui via include_router."""

from fastapi import APIRouter

from app.api import health, profiles

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(profiles.router, tags=["profiles"])
