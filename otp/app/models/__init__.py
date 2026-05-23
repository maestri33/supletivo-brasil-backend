"""Models do schema `otp` (SQLAlchemy 2)."""

from app.models.otp import OTPLog
from app.models.pending_notify import PendingNotify
from app.models.rate_limit import RateLimit

__all__ = ["OTPLog", "PendingNotify", "RateLimit"]
