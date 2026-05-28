"""Model Lead — usuário cujo role atual é 'lead'."""

import enum
from uuid import UUID

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class LeadStatus(str, enum.Enum):
    CAPTURED = "captured"
    WAITING = "waiting"
    CHECKOUT = "checkout"
    COMPLETED = "completed"
    FAILED = "failed"  # BG task de criar checkout esgotou retries; front polla /waiting e recebe error_code.


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID opaco do usuário emitido pelo auth (referência lógica, sem FK §4)",
    )

    status: Mapped[LeadStatus] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            schema="lead",
            create_type=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=LeadStatus.CAPTURED,
        nullable=False,
        index=True,
    )

    promoter_external_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID do promotor/parceiro responsável pela captação",
    )

    failed_reason: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="Código curto do erro quando status=FAILED (ex.: checkout_create_failed). Lido pelo /waiting.",
    )

    def __repr__(self) -> str:
        return f"<Lead {self.external_id} status={self.status}>"
