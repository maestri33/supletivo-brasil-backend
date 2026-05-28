"""
Domain exceptions.

Raise these in the `services/` layer. The global handler in `main.py`
converts them to HTTP responses — services must NOT import HTTPException.
"""


class DomainError(Exception):
    """Base class for all domain exceptions in this service."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


NotFound = NotFoundError  # backward-compat alias


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


Conflict = ConflictError  # backward-compat alias


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class RateLimitExceededError(DomainError):
    """Rate limit do OTP atingido pra um external_id."""

    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(self, message: str = "", retry_after_s: int = 0) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


RateLimitExceeded = RateLimitExceededError  # backward-compat alias


class IntegrationError(DomainError):
    """Failure calling an external service via HTTP."""

    status_code = 502
    code = "integration_error"


class NotifyTransientError(IntegrationError):
    """Erro temporário no notify — pode ser reenfileirado."""


class NotifyPermanentError(IntegrationError):
    """Erro permanente no notify — contact não existe, etc. Não retry."""
