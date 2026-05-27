"""Agrega todos os routers do enrollment (cada um com seu próprio prefixo)."""

from fastapi import APIRouter

from app.api.authenticated.address import router as address_router
from app.api.authenticated.documents import router as documents_router
from app.api.authenticated.education import router as education_router
from app.api.authenticated.profile import router as profile_router
from app.api.authenticated.release import router as release_router
from app.api.authenticated.selfie import router as selfie_router
from app.api.enrollments import router as enrollments_router
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()

# Públicas / desmilitarizadas (consumo interno)
api_router.include_router(webhooks_router)
api_router.include_router(enrollments_router)
api_router.include_router(health_router)

# Autenticadas — funil da matrícula
api_router.include_router(profile_router)
api_router.include_router(address_router)
api_router.include_router(documents_router)
api_router.include_router(education_router)
api_router.include_router(selfie_router)

# Autenticada — coordenador libera a matrícula
api_router.include_router(release_router)
