"""Schemas Pydantic para o serviço Commissions (Parte B — Sprint futuro).

CONVENTION §2 exige Pydantic 2.8+.
"""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Classe base para todos os schemas da API.

    Comportamentos comuns:
    - Ignorar campos extras (extra='ignore')
    - Remover espaços em branco nas bordas de strings (str_strip_whitespace=True)
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


from .commission import (  # noqa: E402
    CommissionCreate,
    CommissionListResponse,
    CommissionResponse,
)
from .error import ErrorResponse  # noqa: E402
from .health import HealthResponse  # noqa: E402
from .payment_batch import (  # noqa: E402
    PaymentBatchListResponse,
    PaymentBatchResponse,
)
from .payout import (  # noqa: E402
    PayoutListResponse,
    PayoutResponse,
)
from .processing import (  # noqa: E402
    TriggerProcessingRequest,
    TriggerProcessingResponse,
)

__all__ = [
    "APIModel",
    "CommissionCreate",
    "CommissionResponse",
    "CommissionListResponse",
    "PaymentBatchResponse",
    "PaymentBatchListResponse",
    "PayoutResponse",
    "PayoutListResponse",
    "TriggerProcessingRequest",
    "TriggerProcessingResponse",
    "HealthResponse",
    "ErrorResponse",
]
