"""Schemas de consulta de logs de chamadas (API + clients externos)."""

from typing import Literal

from app.schemas import APIModel


class LogQuery(APIModel):
    """Parametros de consulta de logs.

    Fields:
        direction: Direcao da chamada ('in' | 'out')
        service: Nome do servico ('auth' | 'notify' | 'data')
        method: Metodo HTTP ('GET' | 'POST' | 'PUT' | 'DELETE')
        status: Codigo de status HTTP
        limit: Maximo de registros por pagina (max 200)
        offset: Deslocamento para paginacao
    """

    direction: Literal["in", "out"] | None = None
    service: str | None = None
    method: str | None = None
    status: int | None = None
    limit: int = 50
    offset: int = 0


class LogEntry(APIModel):
    """Entrada individual de log.

    Fields:
        timestamp: ISO timestamp da chamada
        direction: Direcao da chamada ('in' | 'out')
        service: Nome do servico
        method: Metodo HTTP
        path: Caminho da requisicao
        status: Codigo de status HTTP
        request_body: Corpo da requisicao (opcional)
        response_body: Corpo da resposta (opcional)
        duration_ms: Duracao da chamada em milissegundos
    """

    timestamp: str
    direction: Literal["in", "out"]
    service: str
    method: str
    path: str
    status: int
    request_body: dict | None = None
    response_body: dict | None = None
    duration_ms: int = 0
