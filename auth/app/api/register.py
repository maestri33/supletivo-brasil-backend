"""Endpoint de registro — cria usuario e provisiona servicos."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.api.check import dispatch_otp, lookup_cpf, lookup_phone
from app.api.deps import DbSession
from app.exceptions import Conflict, IntegrationError, ValidationError
from app.integrations.address import AddressClient
from app.integrations.documents import DocumentsClient
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient
from app.integrations.roles import RolesClient
from app.models.user import User
from app.utils.validation import validate_cpf, validate_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/register", tags=["register"])


class RegisterRequest(BaseModel):
    role: str
    phone: str
    cpf: str


@router.post(
    "",
    status_code=201,
    summary="Registra novo usuario — sincrono ate criacao, async para provisionamento",
)
async def register(data: RegisterRequest, bg: BackgroundTasks, db: DbSession) -> dict:
    # 1. Validate role is entry-level
    await _validate_entry_role(data.role)

    # 2. Validate CPF locally + remotely
    try:
        validate_cpf(data.cpf)
    except ValueError as exc:
        raise ValidationError(str(exc), code="CPF_INVALID")

    try:
        cpf_result = await lookup_cpf(data.cpf)
    except IntegrationError:
        raise
    except ValidationError:
        raise
    except Exception as exc:
        raise IntegrationError(
            f"Servico de validacao de CPF indisponivel: {exc}",
            code="PROFILES_UNAVAILABLE",
        )

    if cpf_result["found"]:
        raise Conflict("CPF ja cadastrado.", code="CPF_EXISTS")
    if not cpf_result.get("valid"):
        raise ValidationError("CPF nao validado pelo servico de perfis.", code="CPF_NOT_VALIDATED")

    # 3. Validate phone locally + remotely
    try:
        validate_phone(data.phone)
    except ValueError as exc:
        raise ValidationError(str(exc), code="PHONE_INVALID")

    try:
        phone_result = await lookup_phone(data.phone)
    except IntegrationError:
        raise
    except ValidationError:
        raise
    except Exception as exc:
        raise IntegrationError(
            f"Servico de validacao de phone indisponivel: {exc}",
            code="NOTIFY_UNAVAILABLE",
        )

    if phone_result["found"]:
        raise Conflict("Phone ja cadastrado.", code="PHONE_EXISTS")
    if not phone_result.get("phone_valid"):
        raise ValidationError(
            "Phone nao validado pelo servico de mensageria.",
            code="PHONE_NOT_VALIDATED",
        )

    # 4. Create user (sync) — COMMIT antes de retornar para evitar race
    # com servicos a jusante (ex.: lead) que tentam inserir FK->auth.users
    # antes do commit do dependency-cleanup do FastAPI.
    external_id = uuid.uuid4()
    user = User(external_id=external_id)
    db.add(user)
    await db.commit()

    # 5. Provision services in background
    bg.add_task(_provision, str(external_id), data.role, data.cpf, data.phone)

    return {"external_id": str(external_id)}


# ── Reusable ──────────────────────────────────────


async def validate_entry_role(role: str) -> None:
    """Verifica se a role pode ser atribuida como primeira role (from_role=None)."""
    await _validate_entry_role(role)


# ── Internal ──────────────────────────────────────


async def _validate_entry_role(role: str) -> None:
    """Verifica se existe regra com from_role=None e to_role=role."""
    import niquests

    from app.config import get_settings

    base = get_settings().ROLES_SERVICE_URL
    async with niquests.AsyncSession() as s:
        resp = await s.get(f"{base}/api/v1/config/roles")
        resp.raise_for_status()
        rules = resp.json()

    entry_rules = [r for r in rules if r.get("to_role") == role and r.get("from_role") is None]
    if not entry_rules:
        raise ValidationError(
            f"Role '{role}' nao e uma role de entrada valida.",
            code="INVALID_ENTRY_ROLE",
        )


async def _provision(external_id: str, role: str, cpf: str, phone: str) -> None:
    """Provisiona servicos externos — fire and forget.

    Cada passo e best-effort (CONVENTION §12): a falha de uma integracao e
    logada e nao impede os passos seguintes nem quebra o registro ja efetivado.
    Documentos e Endereco sao criados vazios (get-or-create) conforme o
    `auth/TODO`. Email nao e provisionado aqui — sua unicidade fica a cargo dos
    servicos a jusante quando o email for coletado.
    """
    try:
        async with RolesClient() as roles:
            await roles.assign(external_id, role)
    except Exception as exc:
        logger.warning(f"[provision] roles falhou para {external_id}: {exc}")

    try:
        async with ProfilesClient() as profiles:
            await profiles.create(external_id, cpf)
    except Exception as exc:
        logger.warning(f"[provision] profile falhou para {external_id}: {exc}")

    try:
        async with NotifyClient() as notify:
            await notify.create_contact(external_id, phone=phone)
    except Exception as exc:
        logger.warning(f"[provision] contato falhou para {external_id}: {exc}")

    try:
        async with DocumentsClient() as documents:
            await documents.ensure(external_id)
    except Exception as exc:
        logger.warning(f"[provision] documentos falhou para {external_id}: {exc}")

    try:
        async with AddressClient() as address:
            await address.ensure(external_id)
    except Exception as exc:
        logger.warning(f"[provision] endereco falhou para {external_id}: {exc}")

    await dispatch_otp(external_id)
