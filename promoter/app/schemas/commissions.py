"""Schemas de leitura das comissoes do promoter (agregadas do servico `commissions`).

O servico `commissions` agora existe (Parte B concluida). Degrada para lista
vazia + available=False quando indisponivel (CONVENTION §12).
"""

from app.schemas import APIModel


class CommissionView(APIModel):
    id: str | None = None
    status: str | None = None
    amount: float | None = None
    created_at: str | None = None


class CommissionListResponse(APIModel):
    total: int
    available: bool
    commissions: list[CommissionView]
