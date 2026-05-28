"""Aggregator router — coordinator service.

Apenas dominio do coordenador: coordinators, training_approvals, enrollment_fees.
Provas, documentos do aluno e diplomas migraram para o servico `student`.
"""

from fastapi import APIRouter

from app.api.coordinator import router as coordinator_router
from app.api.fees import router as fees_router
from app.api.health import router as health_router
from app.api.training import router as training_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(coordinator_router, prefix="/api/v1")
api_router.include_router(training_router, prefix="/api/v1")
api_router.include_router(fees_router, prefix="/api/v1")
