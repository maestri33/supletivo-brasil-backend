"""Excecoes de dominio da aplicacao.

Todas herdam de DomainError, que possui status_code e code.
O handler global em main.py converte DomainError em JSONResponse.
"""


class DomainError(Exception):
    """Base para todas as excecoes de dominio."""

    def __init__(self, detail: str, status_code: int = 400, code: str = "DOMAIN_ERROR") -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class NotFoundError(DomainError):
    """Recurso nao encontrado (404)."""

    def __init__(self, detail: str = "Recurso nao encontrado", code: str = "NOT_FOUND") -> None:
        super().__init__(detail, 404, code)


# backward-compat alias
NotFound = NotFoundError


class ConflictError(DomainError):
    """Conflito de estado (409)."""

    def __init__(self, detail: str = "Conflito", code: str = "CONFLICT") -> None:
        super().__init__(detail, 409, code)


# backward-compat alias
Conflict = ConflictError


class ValidationError(DomainError):
    """Erro de validacao (422)."""

    def __init__(self, detail: str = "Erro de validacao", code: str = "VALIDATION_ERROR") -> None:
        super().__init__(detail, 422, code)


class UnauthorizedError(DomainError):
    """Falha de autenticacao — token ausente, invalido ou expirado (401).
    Diferente de ForbiddenError (403), que indica identidade conhecida mas sem permissao."""

    def __init__(self, detail: str = "Nao autenticado", code: str = "UNAUTHORIZED") -> None:
        super().__init__(detail, 401, code)


class ForbiddenError(DomainError):
    """Acesso proibido (403)."""

    def __init__(self, detail: str = "Acesso proibido", code: str = "FORBIDDEN") -> None:
        super().__init__(detail, 403, code)


class IntegrationError(DomainError):
    """Erro em servico externo (502)."""

    def __init__(self, detail: str = "Erro de integracao", code: str = "INTEGRATION_ERROR") -> None:
        super().__init__(detail, 502, code)
