"""Exceções de domínio do serviço de Roles."""


class DomainError(Exception):
    """Base para erros de domínio."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code


class NotFound(DomainError):
    def __init__(self, message: str, code: str = "NOT_FOUND"):
        super().__init__(message, code)


class ValidationError(DomainError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message, code)
