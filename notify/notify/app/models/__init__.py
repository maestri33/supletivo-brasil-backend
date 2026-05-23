"""Models do schema `notify` (SQLAlchemy 2)."""

from app.models.contact import Contact
from app.models.log import Log
from app.models.message import (
    Message,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    STATUS_SKIPPED,
)
from app.models.template import DEFAULT_SLUG, Template

__all__ = [
    "Contact",
    "Log",
    "Message",
    "Template",
    "DEFAULT_SLUG",
    "STATUS_PENDING",
    "STATUS_SENT",
    "STATUS_FAILED",
    "STATUS_SKIPPED",
]
