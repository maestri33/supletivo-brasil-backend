"""Agrega os routers da API do training (cada um com seu proprio prefixo)."""

from fastapi import APIRouter

from app.api.authenticated.coordinator import router as coordinator_router
from app.api.authenticated.materials import router as materials_progress_router
from app.api.authenticated.submissions import router as submissions_router
from app.api.demilitarized.materials import router as materials_router
from app.api.health import router as health_router

api_router = APIRouter()

# Desmilitarizadas (uso interno da plataforma — autoria de materias)
api_router.include_router(materials_router)

# Autenticadas (JWT obrigatorio — trainee submete / consulta progresso)
api_router.include_router(submissions_router)
api_router.include_router(materials_progress_router)

# Autenticadas (JWT obrigatorio — coordenador aprova/rejeita entrevista)
api_router.include_router(coordinator_router)

# Health
api_router.include_router(health_router)
