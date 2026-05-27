"""Serviço de Profile — CRUD atômico (SQLAlchemy 2)."""

import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.exceptions import Conflict, NotFound, ValidationError
from app.integrations.cpfhub import CPFHubClient, CPFHubIdentity
from app.models.birth_info import BirthInfo
from app.models.educational import Educational
from app.models.profile import Profile
from app.schemas.profile import (
    CPFCheckResponse,
    FirstNameResponse,
    ProfileCreate,
    ProfileListItem,
    ProfilePatch,
    ProfileRead,
    build_profile_read,
)
from app.utils.logging import get_logger
from app.validators.cpf import validate_cpf
from app.validators.name import normalize_name

logger = get_logger(__name__)

_PROFILE_FIELDS = {
    "name",
    "gender",
    "mother_name",
    "father_name",
    "blood_type",
    "civil_status",
    "description",
}
_EDUCATIONAL_FIELDS = {
    "level",
    "last_elementary_year",
    "elementary_completed",
    "elementary_year",
    "last_high_school_year",
    "high_school_completed",
}
_BIRTH_INFO_FIELDS = {"state", "city", "birth_date"}


async def _get_profile_with_relations(session: AsyncSession, external_id: UUID) -> Profile | None:
    return await session.scalar(
        select(Profile)
        .where(Profile.external_id == external_id)
        .options(selectinload(Profile.educational), selectinload(Profile.birth_info))
    )


async def create_profile(session: AsyncSession, data: ProfileCreate) -> ProfileRead:
    """Cria perfil atômico delegando uniqueness e FK ao Postgres.

    Sem SELECT prévio — duas requisições concorrentes com mesmo CPF/external_id
    podem passar o check e quebrar no INSERT. Confiamos nos UNIQUE constraints
    e na FK cross-schema; IntegrityError vira 409 (duplicado) ou 422 (FK).
    """
    profile = Profile(external_id=data.external_id, cpf=data.cpf)
    session.add(profile)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _classify_integrity_error(exc, data) from exc

    await session.refresh(profile)

    birth_info = await _enrich_from_cpfhub(session, profile)
    return build_profile_read(profile, None, birth_info)


def _classify_integrity_error(
    exc: IntegrityError,
    data: ProfileCreate,
) -> Conflict | ValidationError:
    """Mapeia IntegrityError do Postgres para o erro de domínio correto.

    Constraints (naming convention de app/db.py):
      - profiles_cpf_key          → UNIQUE cpf
      - profiles_external_id_key  → UNIQUE external_id
      - profiles_external_id_fkey → FK auth.users.external_id
    """
    msg = str(getattr(exc, "orig", exc)).lower()
    if "profiles_cpf_key" in msg or '"cpf"' in msg:
        return Conflict(f'CPF "{data.cpf}" já está em uso')
    if "profiles_external_id_key" in msg:
        return Conflict(f'external_id "{data.external_id}" já existe')
    if "profiles_external_id_fkey" in msg or "foreign key" in msg:
        return ValidationError(
            f'external_id "{data.external_id}" não existe em auth.users',
        )
    # Constraint desconhecido — devolve genérico mas estruturado em vez de 500.
    return ValidationError("Falha de integridade ao criar profile")


async def _enrich_from_cpfhub(
    session: AsyncSession,
    profile: Profile,
) -> BirthInfo | None:
    """Pós-save: enriquece o profile com dados da CPFHub.io. Best-effort.

    Qualquer falha (rede, 4xx, 5xx, parse, integridade) é engolida — o profile
    recém-criado continua válido sem enriquecimento. Não loga PII.
    """
    settings = get_settings()
    if not settings.cpfhub_api_key:
        return None

    try:
        async with CPFHubClient(
            api_key=settings.cpfhub_api_key,
            base_url=settings.cpfhub_base_url,
            timeout=settings.cpfhub_timeout_seconds,
        ) as client:
            identity = await client.lookup(profile.cpf)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("cpfhub.unexpected_error", error=type(exc).__name__)
        return None

    if identity is None:
        return None

    birth_info = _apply_identity(session, profile, identity)
    if birth_info is None and profile.name is None and profile.gender is None:
        return None

    try:
        await session.commit()
        await session.refresh(profile)
    except SQLAlchemyError as exc:
        logger.warning("cpfhub.persist_failed", error=type(exc).__name__)
        await session.rollback()
        return None

    return birth_info


def _apply_identity(
    session: AsyncSession,
    profile: Profile,
    identity: CPFHubIdentity,
) -> BirthInfo | None:
    """Aplica os campos da CPFHub no profile. Retorna BirthInfo se criado."""
    if identity.name:
        try:
            clean = normalize_name(identity.name)
        except Exception:  # noqa: BLE001
            clean = None
        if clean and len(clean) <= 200:
            profile.name = clean

    if identity.gender in ("M", "F"):
        profile.gender = identity.gender

    if identity.birth_date is None:
        return None

    birth_info = BirthInfo(profile_id=profile.id, birth_date=identity.birth_date)
    session.add(birth_info)
    return birth_info


async def get_profile(session: AsyncSession, external_id: UUID) -> ProfileRead:
    profile = await _get_profile_with_relations(session, external_id)
    if not profile:
        raise NotFound(f'Profile "{external_id}" não encontrado')
    return build_profile_read(profile, profile.educational, profile.birth_info)


async def get_profile_by_cpf(session: AsyncSession, cpf: str) -> CPFCheckResponse:
    cpf_valid = True
    try:
        validate_cpf(cpf)
    except ValidationError:
        cpf_valid = False

    profile = await session.scalar(select(Profile).where(Profile.cpf == cpf).limit(1))
    if profile:
        return CPFCheckResponse(external_id=profile.external_id, found=True, valid=True)
    return CPFCheckResponse(external_id=None, found=False, valid=cpf_valid)


async def list_profiles(
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    cpf: str | None = None,
) -> list[ProfileListItem]:
    """Lista perfis com paginação e filtros opcionais.

    - `limit`: 1..100 (default 20). Maiores valores são truncados para 100.
    - `offset`: >= 0.
    - `q`: prefix-search case-insensitive em `name`.
    - `cpf`: prefix-match exato (string), aceita CPF com ou sem pontuação.
    """
    capped_limit = max(1, min(int(limit or 20), 100))
    safe_offset = max(0, int(offset or 0))

    stmt = select(Profile)

    if q:
        q_clean = q.strip()
        if q_clean:
            pattern = f"{q_clean}%"
            stmt = stmt.where(func.lower(Profile.name).like(func.lower(pattern)))

    if cpf:
        digits = re.sub(r"[^0-9]", "", cpf)
        if digits:
            stmt = stmt.where(Profile.cpf.like(f"{digits}%"))

    stmt = stmt.order_by(Profile.created_at.desc()).limit(capped_limit).offset(safe_offset)

    result = await session.scalars(stmt)
    return [
        ProfileListItem(external_id=p.external_id, cpf=p.cpf, name=p.name) for p in result.all()
    ]


async def patch_profile(
    session: AsyncSession,
    external_id: UUID,
    data: ProfilePatch,
) -> ProfileRead:
    profile = await _get_profile_with_relations(session, external_id)
    if not profile:
        raise NotFound(f'Profile "{external_id}" não encontrado')

    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field in _PROFILE_FIELDS:
            setattr(profile, field, value)

    edu_updates = {k: v for k, v in updates.items() if k in _EDUCATIONAL_FIELDS}
    if edu_updates:
        if profile.educational is None:
            profile.educational = Educational(profile_id=profile.id)
            session.add(profile.educational)
        for field, value in edu_updates.items():
            setattr(profile.educational, field, value)

    bi_updates = {k: v for k, v in updates.items() if k in _BIRTH_INFO_FIELDS}
    if bi_updates:
        if profile.birth_info is None:
            profile.birth_info = BirthInfo(profile_id=profile.id)
            session.add(profile.birth_info)
        for field, value in bi_updates.items():
            setattr(profile.birth_info, field, value)

    await session.commit()
    await session.refresh(profile)
    return build_profile_read(profile, profile.educational, profile.birth_info)


async def get_first_name(session: AsyncSession, external_id: UUID) -> FirstNameResponse:
    profile = await session.scalar(select(Profile).where(Profile.external_id == external_id))
    if not profile:
        raise NotFound(f'Profile "{external_id}" não encontrado')

    name = (profile.name or "").strip()
    if not name:
        return FirstNameResponse(first_name=None, full_name=None)

    parts = name.split()
    return FirstNameResponse(first_name=parts[0], full_name=name)


async def delete_profile(session: AsyncSession, external_id: UUID) -> None:
    profile = await session.scalar(select(Profile).where(Profile.external_id == external_id))
    if not profile:
        raise NotFound(f'Profile "{external_id}" não encontrado')
    await session.delete(profile)
    await session.commit()
