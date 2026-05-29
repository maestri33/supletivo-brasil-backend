"""Agregador de rotas."""

from fastapi import APIRouter

from app.api.atomic import router as atomic_router
from app.api.check import router as check_router
from app.api.health import router as health_router
from app.api.log import router as log_router
from app.api.login import router as login_router
from app.api.recover import router as recover_router
from app.api.register import router as register_router

api_router = APIRouter()

api_router.include_router(atomic_router, prefix="/api/v1")
api_router.include_router(check_router, prefix="/api/v1")
api_router.include_router(log_router, prefix="/api/v1")
api_router.include_router(login_router, prefix="/api/v1")
api_router.include_router(recover_router, prefix="/api/v1")
api_router.include_router(register_router, prefix="/api/v1")
api_router.include_router(health_router)
