"""Rate limit por external_id — tabela `otp.rate_limit`.

Duas regras:
1. Janela curta: 1 OTP a cada `OTP_RATELIMIT_WINDOW_S` segundos.
2. Janela horária: no máximo `OTP_RATELIMIT_HOURLY_MAX` OTPs por hora.

A política é checada e gravada na MESMA transação (UPSERT atômico).
Se qualquer limite estoura, levanta `RateLimitExceeded` com retry_after_s.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import RateLimitExceeded
from app.models.rate_limit import RateLimit
from app.utils.logging import get_logger

log = get_logger(__name__)
settings = get_settings()


async def check_and_record(session: AsyncSession, external_id: UUID) -> None:
    """Aplica as duas regras de rate limit. Comita a janela atualizada.

    Levanta RateLimitExceeded se bloqueado — nesse caso nada é alterado.
    """
    now = datetime.now(UTC)
    window_s = settings.otp_ratelimit_window_s
    hourly_max = settings.otp_ratelimit_hourly_max

    existing = await session.scalar(select(RateLimit).where(RateLimit.external_id == external_id))

    if existing is not None:
        # ── regra 1: janela curta ──
        elapsed_s = (now - existing.last_created_at).total_seconds()
        if elapsed_s < window_s:
            retry_after = max(1, int(window_s - elapsed_s))
            log.info(
                "otp.rate_limit.window_blocked",
                external_id=str(external_id),
                retry_after_s=retry_after,
            )
            raise RateLimitExceeded(
                f"Aguarde {retry_after}s antes de gerar outro OTP.",
                retry_after_s=retry_after,
            )

        # ── regra 2: janela horária ──
        hourly_elapsed_s = (now - existing.hourly_window_start).total_seconds()
        if hourly_elapsed_s < 3600:
            if existing.hourly_count >= hourly_max:
                retry_after = max(1, int(3600 - hourly_elapsed_s))
                log.info(
                    "otp.rate_limit.hourly_blocked",
                    external_id=str(external_id),
                    count=existing.hourly_count,
                    retry_after_s=retry_after,
                )
                raise RateLimitExceeded(
                    f"Limite de {hourly_max} OTPs/hora atingido. Aguarde {retry_after}s.",
                    retry_after_s=retry_after,
                )
            new_hourly_count = existing.hourly_count + 1
            new_window_start = existing.hourly_window_start
        else:
            new_hourly_count = 1
            new_window_start = now
    else:
        new_hourly_count = 1
        new_window_start = now

    stmt = pg_insert(RateLimit).values(
        external_id=external_id,
        last_created_at=now,
        hourly_count=new_hourly_count,
        hourly_window_start=new_window_start,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateLimit.external_id],
        set_={
            "last_created_at": stmt.excluded.last_created_at,
            "hourly_count": stmt.excluded.hourly_count,
            "hourly_window_start": stmt.excluded.hourly_window_start,
        },
    )
    await session.execute(stmt)
    await session.commit()

    log.info(
        "otp.rate_limit.accepted",
        external_id=str(external_id),
        hourly_count=new_hourly_count,
    )


async def reset(session: AsyncSession, external_id: UUID) -> None:
    """Limpa a entrada de rate limit pra um external_id (uso debug/admin)."""
    rl = await session.scalar(select(RateLimit).where(RateLimit.external_id == external_id))
    if rl is None:
        return
    await session.delete(rl)
    await session.commit()
    log.info("otp.rate_limit.reset", external_id=str(external_id))
