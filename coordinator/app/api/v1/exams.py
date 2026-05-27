"""Exams API endpoints — v1 route module."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/exams/health")
async def _health():
    return {"status": "ok", "module": "exams"}
