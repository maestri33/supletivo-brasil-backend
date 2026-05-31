"""Etapa profile — orquestra o serviço `profiles` e avança o status.

CONVENTION §6: o enrollment não duplica dados pessoais — só PATCH em
`profiles` (dono) e avança `started → profile`.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations.profiles import ProfilesClient
from app.models import EnrollmentStatus
from app.schemas.profile import ProfilePostRequest
from app.services import enrollment as enrollment_svc

settings = get_settings()

_PROFILE_FIELDS = (
    "gender",
    "mother_name",
    "father_name",
    "marital_status",
    "date_of_birth",
    "birthplace",
    "nationality",
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.profiles_base_url, timeout=settings.http_timeout)


async def get_profile(external_id: str) -> dict:
    async with _client() as http:
        data = await ProfilesClient(http).get_one(external_id)
    return {f: data.get(f) for f in _PROFILE_FIELDS}


async def save_profile(
    session: AsyncSession,
    external_id: str,
    payload: ProfilePostRequest,
) -> str:
    """PATCH em `profiles` + avanço de status started → profile."""
    fields = payload.model_dump()
    # Date precisa virar string ISO antes de serializar JSON.
    if fields.get("date_of_birth"):
        fields["date_of_birth"] = fields["date_of_birth"].isoformat()

    async with _client() as http:
        await ProfilesClient(http).patch(external_id, **fields)

    enrollment = await enrollment_svc.get(session, external_id)
    if not enrollment:
        raise NotFound("Matrícula não encontrada")
    enrollment_svc.advance(enrollment, EnrollmentStatus.STARTED, EnrollmentStatus.PROFILE)
    return enrollment.status
