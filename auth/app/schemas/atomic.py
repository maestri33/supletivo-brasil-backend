"""Schema de limpeza atomica do ecossistema — two-step para evitar acidentes."""

from app.schemas import APIModel


class AtomicCreateResponse(APIModel):
    """Resposta da criacao de token de limpeza atomica.

    Fields:
        atomic_id: Token UUID para confirmacao da limpeza
        ttl: Tempo de vida do token em segundos
        message: Instrucao para confirmar a limpeza
    """

    atomic_id: str
    ttl: int
    message: str
