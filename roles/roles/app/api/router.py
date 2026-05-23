"""Agregação de routers."""

from fastapi import APIRouter

from app.api.config import router as config_router
from app.api.role import router as role_router
from app.api.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(role_router)
router.include_router(config_router)
router.include_router(users_router)
