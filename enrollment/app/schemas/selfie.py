"""Schemas da etapa selfie — assinatura digital (mesma lógica do candidate).

Upload multipart (sem body JSON); validação heurística via `ai/vision`
best-effort (não bloqueia se `ai` cair, CONVENTION §13).
"""

from app.schemas import APIModel


class SelfieGetResponse(APIModel):
    message: str = "Envie uma selfie real para concluir o envio de dados"
    has_selfie: bool = False


class SelfiePostResponse(APIModel):
    status: str
    message: str = (
        "Selfie aceita. Sua matrícula está aguardando a liberação do coordenador."
    )
    verified: bool = False
    description: str | None = None
