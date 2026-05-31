# Convenção §3: api_router agrega TODOS os sub-routers do serviço.
# Monta: webhooks + enrollments + health + funil autenticado + release.
# enrollment NÃO tem rotas públicas (matrícula é sempre autenticada via JWT).
# Comentários em pt-br (§15); identificadores em inglês.
from fastapi import APIRouter

from app.api.enrollments import router as enrollments_router
from app.api.webhooks import router as webhooks_router
from app.api.health import router as health_router
from app.api.authenticated.profile import router as profile_router
from app.api.authenticated.address import router as address_router
from app.api.authenticated.documents import router as documents_router
from app.api.authenticated.education import router as education_router
from app.api.authenticated.selfie import router as selfie_router
from app.api.authenticated.release import router as release_router

api_router = APIRouter()
api_router.include_router(webhooks_router)
api_router.include_router(enrollments_router)
api_router.include_router(health_router)
api_router.include_router(profile_router)
api_router.include_router(address_router)
api_router.include_router(documents_router)
api_router.include_router(education_router)
api_router.include_router(selfie_router)
api_router.include_router(release_router)
