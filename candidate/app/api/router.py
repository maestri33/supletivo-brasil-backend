"""Agrega todos os routers da API do candidate (cada um com seu proprio prefixo)."""

from fastapi import APIRouter

from app.api.authenticated.address import router as address_router
from app.api.authenticated.birth import router as birth_router
from app.api.authenticated.captured import router as captured_router
from app.api.authenticated.documents import router as documents_router
from app.api.authenticated.educational import router as educational_router
from app.api.authenticated.personal import router as personal_router
from app.api.authenticated.pixkey import router as pixkey_router
from app.api.authenticated.selfie import router as selfie_router
from app.api.demilitarized.candidates import router as candidates_router
from app.api.public.auth import router as auth_router

api_router = APIRouter()

# Publicas
api_router.include_router(auth_router)

# Autenticadas (funil, na ordem das etapas)
api_router.include_router(captured_router)
api_router.include_router(personal_router)
api_router.include_router(educational_router)
api_router.include_router(birth_router)
api_router.include_router(address_router)
api_router.include_router(documents_router)
api_router.include_router(pixkey_router)
api_router.include_router(selfie_router)

# Desmilitarizadas (uso interno)
api_router.include_router(candidates_router)
