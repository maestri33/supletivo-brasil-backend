"""Modelos ORM (SQLAlchemy). Importados centralmente para descoberta pelo Alembic."""

from app.models.user import Base, User, UserRole

__all__ = ["Base", "User", "UserRole"]
