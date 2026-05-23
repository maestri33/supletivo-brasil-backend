"""
Aggregator router.

Every new feature adds its router here via include_router.
"""

from fastapi import APIRouter

from app.api import health, otp, webhook

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(otp.router, tags=["otp"])
api_router.include_router(webhook.router, tags=["webhook"])
