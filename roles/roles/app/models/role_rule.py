"""RoleRule — regras de transição entre roles (SQLAlchemy 2)."""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RoleRule(Base):
    __tablename__ = "role_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    from_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_role: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, comment="add | replace")
    requires_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    forbids_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
