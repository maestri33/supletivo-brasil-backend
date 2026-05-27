"""Agrega todos os routers da API do promoter (cada um com seu proprio prefixo)."""

from fastapi import APIRouter

from app.api.authenticated.me import router as me_router
from app.api.demilitarized.promoters import router as promoters_router
from app.api.public.auth import router as auth_router

api_router = APIRouter()

# Publicas
api_router.include_router(auth_router)

# Autenticadas (visao do proprio promoter)
api_router.include_router(me_router)

# Desmilitarizadas (uso interno)
api_router.include_router(promoters_router)
