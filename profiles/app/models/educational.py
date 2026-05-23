"""Educational — OneToOne com Profile (SQLAlchemy 2)."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Educational(Base):
    __tablename__ = "educational"

    LEVEL_ELEM_INC = "elementary_incomplete"
    LEVEL_ELEM_COMP = "elementary_complete"
    LEVEL_HS_INC = "high_school_incomplete"
    LEVEL_HS_COMP = "high_school_complete"
    LEVEL_HIGHER_INC = "higher_incomplete"
    LEVEL_HIGHER_COMP = "higher_complete"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("profiles.profiles.id", ondelete="CASCADE", name="educational_profile_id_fkey"),
        unique=True,
        index=True,
        nullable=False,
    )

    level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_elementary_year: Mapped[str | None] = mapped_column(String(10), nullable=True)
    elementary_completed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    elementary_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_high_school_year: Mapped[str | None] = mapped_column(String(15), nullable=True)
    high_school_completed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="educational")  # noqa: F821
