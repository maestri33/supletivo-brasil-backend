"""
Excecoes de dominio.

Levante estas excecoes na camada `services/`. O handler global em `main.py`
converte em HTTPException — services NAO devem importar HTTPException.
"""


class DomainError(Exception):
    """Base de todas as excecoes de dominio deste servico."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class PixKeyError(ValidationError):
    """Erro de validacao de chave Pix (formato, DICT, holder)."""

    code = "pixkey_error"


class PaymentError(ValidationError):
    """Erro na criacao ou processamento de pagamento."""

    code = "payment_error"
