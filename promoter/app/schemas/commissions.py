"""Schemas de leitura das comissoes do promoter (agregadas do servico `commissions`).

`commissions` ainda nao existe (so' spec/TODO). A visao degrada para vazia +
`available=False` quando o servico nao responde — nunca quebra (CONVENTION §12).
Os campos sao um passthrough tolerante; o contrato real sera' fixado quando o
servico `commissions` for construido.
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
