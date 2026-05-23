"""config/url: set and verify the externally-reachable URL.

Flow:
  1. POST /config/url { url } -> server creates nonce, stores (target_url, nonce),
     returns verify_url = `${url.rstrip('/')}/config/url/verify/${nonce}`.
  2. Client (usually the user's browser) opens verify_url on the user's own infra.
     That infra calls back GET /config/url/verify/{nonce} on this app to prove reachability.
  3. On consume: mark nonce, persist URL to ConfigKV.

The nonce is single-use and expires in url_verify_nonce_ttl seconds.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..config import get_settings
from ..exceptions import ValidationError
from ..models import UrlVerifyNonce

VERIFY_PATH = "/api/v1/config/url/verify"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def issue_nonce(db: Session, url: str) -> tuple[str, str]:
    """Create a nonce bound to url. Returns (nonce, verify_url)."""
    # Invalidate previous pending nonces (hygiene, not required)
    db.query(UrlVerifyNonce).filter(
        UrlVerifyNonce.consumed_at.is_(None),
    ).delete(synchronize_session=False)

    nonce = secrets.token_urlsafe(24)
    row = UrlVerifyNonce(nonce=nonce, target_url=str(url), purpose="external")
    db.add(row)
    db.flush()

    verify_url = f"{str(url).rstrip('/')}{VERIFY_PATH}/{nonce}"
    return nonce, verify_url


def consume_nonce(db: Session, nonce: str) -> UrlVerifyNonce:
    """Validate + single-use mark the nonce. Raises ValidationError on problems."""
    row = db.get(UrlVerifyNonce, nonce)
    if row is None:
        raise ValidationError("nonce_not_found")
    if row.consumed_at is not None:
        raise ValidationError("nonce_already_used")
    age = _now() - row.created_at
    if age > timedelta(seconds=get_settings().url_verify_nonce_ttl):
        raise ValidationError("nonce_expired")
    row.consumed_at = _now()
    db.flush()

    cfg.set_(db, cfg.K_EXTERNAL_URL, row.target_url)
    return row
