"""Diplomas API endpoints — v1 route module."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/diplomas/health")
async def _health():
    return {"status": "ok", "module": "diplomas"}
