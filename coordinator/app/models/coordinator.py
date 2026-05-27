"""Model Coordinator — coordenador de polo.

Cada coordenador pertence a um hub (polo) e tem um external_id que
referencia auth.users. Coordena operacoes academicas locais.
"""

import enum
from uuid import uuid4

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin

UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


class CoordinatorStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class Coordinator(Base, TimestampMixin):
    __tablename__ = "coordinators"

    id: Mapped[str] = mapped_column(
        UUIDStr, primary_key=True, default=lambda: str(uuid4())
    )
    external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, unique=True, comment="FK logica -> auth.users"
    )
    hub_external_id: Mapped[str] = mapped_column(
        UUIDStr, nullable=False, comment="FK logica -> hub.hubs"
    )
    status: Mapped[CoordinatorStatus] = mapped_column(
        Enum(CoordinatorStatus, name="coordinator_status"),
        nullable=False,
        default=CoordinatorStatus.active,
        server_default="active",
    )

    def __repr__(self) -> str:
        return f"<Coordinator {self.id} hub={self.hub_external_id}>"
