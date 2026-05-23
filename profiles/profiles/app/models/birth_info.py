"""BirthInfo — OneToOne com Profile (SQLAlchemy 2)."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BirthInfo(Base):
    __tablename__ = "birth_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("profiles.profiles.id", ondelete="CASCADE", name="birth_info_profile_id_fkey"),
        unique=True,
        index=True,
        nullable=False,
    )

    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="birth_info")  # noqa: F821
