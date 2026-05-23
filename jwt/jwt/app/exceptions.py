"""
Excecoes de dominio do microsservico JWT.

Estas excecoes representam ERROS DE NEGOCIO — nao erros tecnicos.
Elas sao levantadas exclusivamente na camada `services/`.

REGRA FUNDAMENTAL:
  Services NUNCA importam HTTPException do FastAPI.
  Em vez disso, levantam uma das excecoes abaixo.
  O handler global em main.py as converte em respostas HTTP padronizadas.

Isso mantem a logica de negocio desacoplada do framework web.
Se um dia o FastAPI for trocado por outro framework, so' o handler
em main.py precisa mudar — os services continuam iguais.

Formato da resposta de erro:
  {"code": "not_found", "message": "Config X nao encontrada"}

Mapeamento excecao → HTTP status:
  DomainError       → 400 Bad Request
  NotFound          → 404 Not Found
  Conflict          → 409 Conflict
  ValidationError   → 422 Unprocessable Entity
  IntegrationError  → 502 Bad Gateway
"""


class DomainError(Exception):
    """
    Base de todas as excecoes de dominio deste servico.

    Atributos:
      status_code: codigo HTTP retornado ao cliente
      code:        codigo de erro legivel por maquina (ex: "not_found")
      message:     mensagem em portugues explicando o erro
    """

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFound(DomainError):
    """Recurso nao encontrado (ex: config JWT com ID inexistente)."""
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    """Conflito de estado (ex: tentar criar config com nome duplicado)."""
    status_code = 409
    code = "conflict"


class ValidationError(DomainError):
    """Dados invalidos a nivel de negocio (ex: refresh token expirado ou adulterado)."""
    status_code = 422
    code = "validation_error"


class IntegrationError(DomainError):
    """
    Falha ao chamar um servico externo.

    Exemplos: API de terceiros fora do ar, fila de mensagens inacessivel,
    webhook que nao respondeu. Nao usado atualmente, mas previsto para
    quando o servico precisar se comunicar com outros sistemas.
    """
    status_code = 502
    code = "integration_error"
