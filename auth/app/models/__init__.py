"""Modelos ORM (SQLAlchemy). Importados centralmente para descoberta pelo Alembic."""

from app.models.user import Base, User

__all__ = ["Base", "User"]
