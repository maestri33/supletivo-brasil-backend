"""Exceções de domínio do serviço enrollment.

Todas herdam de DomainError (status_code + code). O handler global em
main.py converte DomainError em JSONResponse `{"detail": ..., "code": ...}`.
Padrão alinhado com os demais serviços v7m (ver auth/app/exceptions.py).
"""


class DomainError(Exception):
    """Base para todas as exceções de domínio."""

    def __init__(
        self, detail: str, status_code: int = 400, code: str = "DOMAIN_ERROR"
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class NotFound(DomainError):
    """Recurso não encontrado (404)."""

    def __init__(
        self, detail: str = "Recurso não encontrado", code: str = "NOT_FOUND"
    ) -> None:
        super().__init__(detail, 404, code)


class Conflict(DomainError):
    """Conflito de estado (409)."""

    def __init__(self, detail: str = "Conflito", code: str = "CONFLICT") -> None:
        super().__init__(detail, 409, code)


class ValidationError(DomainError):
    """Erro de validação (422)."""

    def __init__(
        self, detail: str = "Erro de validação", code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(detail, 422, code)
