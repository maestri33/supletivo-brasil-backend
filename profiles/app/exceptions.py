"""
Exceções de domínio.

Lance estas exceções na camada `services/`. O handler global em `main.py`
converte para HTTPException — services NÃO devem importar HTTPException.
"""


class DomainError(Exception):
    """Base de todas as exceções de domínio deste serviço."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFound(DomainError):
    """Recurso não encontrado."""

    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    """Conflito — recurso duplicado (CPF, external_id)."""

    status_code = 409
    code = "conflict"


class ValidationError(DomainError):
    """Erro de validação — campo inválido, CPF com dígito errado, etc."""

    status_code = 422
    code = "validation_error"


class IntegrationError(DomainError):
    """Falha ao chamar serviço externo (HTTP, fila, webhook)."""

    status_code = 502
    code = "integration_error"
