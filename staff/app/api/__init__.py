"""API de staff."""

from app.api.health import HealthOut
from app.api.authenticated import authenticated_router

__all__ = ["HealthOut", "authenticated_router"]
