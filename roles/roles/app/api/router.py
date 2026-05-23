"""Agregação de routers."""

from fastapi import APIRouter

from app.api.role_rules import router as role_rules_router
from app.api.role import router as role_router
from app.api.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(role_router)
router.include_router(role_rules_router)
router.include_router(users_router)
