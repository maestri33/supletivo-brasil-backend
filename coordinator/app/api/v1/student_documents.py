"""Student documents API endpoints — v1 route module."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/student-documents/health")
async def _health():
    return {"status": "ok", "module": "student_documents"}
