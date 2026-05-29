"""Re-exports all schema modules for backward compatibility."""

from __future__ import annotations

from .charge import (
    ChargeCreateRequest,
    ChargePixData,
    ChargeResponse,
    CustomerInline,
    CustomerResponse,
)
from .config import (
    ConfigConfirmResponse,
    ConfigInternalResponse,
    ConfigStatusResponse,
    SetInternalUrlRequest,
    SetKeyRequest,
    SetKeyResponse,
    SetUrlRequest,
    SetUrlResponse,
)
from .payment import PaymentResponse, QRCodeAnalyzeResponse
from .pixkey import PixKeyCheckResponse, PixKeyResponse
from .shared import ERROR_CODES, ErrorResponse, OkResponse, responses_for
from .webhook import InternalNotification

__all__ = [
    "ChargeCreateRequest",
    "ChargePixData",
    "ChargeResponse",
    "ConfigConfirmResponse",
    "ConfigInternalResponse",
    "ConfigStatusResponse",
    "CustomerInline",
    "CustomerResponse",
    "ERROR_CODES",
    "ErrorResponse",
    "InternalNotification",
    "OkResponse",
    "PaymentResponse",
    "PixKeyCheckResponse",
    "PixKeyResponse",
    "QRCodeAnalyzeResponse",
    "SetInternalUrlRequest",
    "SetKeyRequest",
    "SetKeyResponse",
    "SetUrlRequest",
    "SetUrlResponse",
    "responses_for",
]
