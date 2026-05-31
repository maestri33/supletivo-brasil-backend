"""Schemas da etapa de selfie (assinatura de contrato).

A imagem e' armazenada no servico `documents` (slot `foto`) e verificada via
`ai` /image/vision (heuristica de rosto humano). Concluida a etapa, o candidato
e' promovido a `training` (servico roles) e o funil encerra em `completed`.
"""

from app.schemas import APIModel


class SelfieGetResponse(APIModel):
    message: str = "Envie uma selfie real para concluir o cadastro"
    has_selfie: bool = False


class SelfiePostResponse(APIModel):
    status: str
    message: str = "Selfie aceita, cadastro concluido"
    verified: bool = False
    description: str | None = None
