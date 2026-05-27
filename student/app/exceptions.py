"""
Excecoes de dominio.

Levante estas excecoes na camada `services/`. O handler global em `main.py`
converte em resposta HTTP — services NAO importam HTTPException.
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


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class StudentNotFound(NotFound):
    code = "student_not_found"


class StudentAlreadyExists(Conflict):
    code = "student_already_exists"
