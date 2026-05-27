"""Profile — entidade raiz (SQLAlchemy 2)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Profile(Base):
    """Apenas external_id e cpf são obrigatórios."""

    __tablename__ = "profiles"

    GENDER_M = "M"
    GENDER_F = "F"

    CIVIL_SINGLE = "single"
    CIVIL_MARRIED = "married"
    CIVIL_WIDOWED = "widowed"
    CIVIL_DIVORCED = "divorced"
    CIVIL_STABLE_UNION = "stable_union"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.users.external_id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="profiles_external_id_fkey",
        ),
        unique=True,
        index=True,
        nullable=False,
    )

    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(3), nullable=True)
    civil_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    birth_info: Mapped["BirthInfo | None"] = relationship(  # noqa: F821
        "BirthInfo",
        uselist=False,
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    educational: Mapped["Educational | None"] = relationship(  # noqa: F821
        "Educational",
        uselist=False,
        back_populates="profile",
        cascade="all, delete-orphan",
    )
