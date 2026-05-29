"""
Excecoes de dominio do microsservico JWT.

Representam ERROS DE NEGOCIO — nao erros tecnicos. Sao levantadas apenas na
camada `services/`; o handler global em `main.py` as converte em respostas HTTP
padronizadas. Services NUNCA importam `HTTPException` do FastAPI — assim a logica
de negocio fica desacoplada do framework web.

Formato da resposta de erro:
  {"code": "validation_error", "message": "Refresh token invalido"}

Mapeamento excecao -> HTTP status:
  DomainError      -> 400 Bad Request
  ValidationError  -> 422 Unprocessable Entity
"""


class DomainError(Exception):
    """
    Base de todas as excecoes de dominio deste servico.

    Atributos:
      status_code: codigo HTTP retornado ao cliente
      code:        codigo de erro legivel por maquina (ex: "validation_error")
      message:     mensagem em portugues explicando o erro
    """

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class ValidationError(DomainError):
    """Dados invalidos a nivel de negocio (ex: refresh token expirado ou adulterado)."""

    status_code = 422
    code = "validation_error"
