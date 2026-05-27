"""V1 API endpoints — coordinator service."""

from fastapi import APIRouter

from app.api.v1.coordinators import router as coordinators_router
from app.api.v1.training_approvals import router as training_approvals_router
from app.api.v1.diplomas import router as diplomas_router
from app.api.v1.exams import router as exams_router
from app.api.v1.enrollment_fees import router as enrollment_fees_router
from app.api.v1.student_documents import router as student_documents_router

router = APIRouter(prefix="/api/v1")

router.include_router(coordinators_router)
router.include_router(training_approvals_router)
router.include_router(diplomas_router)
router.include_router(exams_router)
router.include_router(enrollment_fees_router)
router.include_router(student_documents_router)
