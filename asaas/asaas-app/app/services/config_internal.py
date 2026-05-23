"""Envio de onboarding doc para a URL interna.

A cada chamada de POST /api/v1/config/internal {url, target}, enviamos um doc
explicando ao sistema interno qual a categoria de evento que vira para aquela URL.
"""

from __future__ import annotations

import httpx

_BASE_DOC = """
# asaas-app -> sua URL interna

Voce recebera POSTs JSON neste endpoint.

## Formato comum da notificacao

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "kind": "pixkey" | "qrcode" | "charge",
  "external_id": "string ou null",
  "status": "..."
}
```

- `kind=pixkey`  -> `external_id` = external_id da pixkey
- `kind=qrcode`  -> `external_id` sempre null
- `kind=charge`  -> `external_id` = external_id do customer (pagador)

## Resposta esperada

Responda com qualquer 2xx. Nao precisa corpo. Falhas nao param o fluxo —
o evento fica registrado no nosso DB mas a operacao continua.
""".strip()

_DOC_BY_TARGET: dict[str, str] = {
    "default": (
        _BASE_DOC + "\n\n## Esta URL recebe TODOS os eventos (catch-all)\n\n"
        "Modo legado: todas as transicoes de status caem aqui. Configure URLs especificas "
        "via target=scheduling, target=payout ou target=charge para granularidade."
    ),
    "scheduling": (
        _BASE_DOC + "\n\n## Esta URL recebe apenas eventos de AGENDAMENTO\n\n"
        "Disparos:\n"
        "- Criacao de payment com `scheduled_for` (status=SCHEDULED)\n"
        "- Transicao automatica SCHEDULED -> QUEUED quando a hora chega\n"
        "Use para acompanhar a fila de execucao programada."
    ),
    "payout": (
        _BASE_DOC + "\n\n## Esta URL recebe status de PAYOUTS PIX (saida)\n\n"
        "kind in (pixkey, qrcode). Disparos: SUBMITTED, AWAITING_BALANCE (1a transicao), "
        "PAID, FAILED, CANCELLED."
    ),
    "charge": (
        _BASE_DOC + "\n\n## Esta URL recebe status de COBRANCAS PIX (entrada)\n\n"
        "kind=charge. Disparos:\n"
        "- PENDING ao criar\n"
        "- PAID quando cliente paga (PAYMENT_CONFIRMED ou PAYMENT_RECEIVED do Asaas)\n"
        "- EXPIRED se passar o due_date sem pagamento\n"
        "- CANCELLED se cancelado manualmente\n"
        "- REFUNDED se houver estorno"
    ),
}


def doc_for_target(target: str) -> str:
    return _DOC_BY_TARGET.get(target, _DOC_BY_TARGET["default"])


def send_onboarding(url: str, *, target: str = "default") -> dict:
    """Envia POST com o doc. Retorna {ok, status_code}. Lanca em falha de rede."""
    payload = {
        "event": "ASAAS_APP_ONBOARDING",
        "target": target,
        "doc": doc_for_target(target),
    }
    with httpx.Client(timeout=10.0) as cli:
        r = cli.post(url, json=payload)
    return {"ok": 200 <= r.status_code < 300, "status_code": r.status_code}
