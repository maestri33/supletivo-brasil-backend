"""
Entrypoint FastAPI.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 80
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import config_store as cfg
from .api.router import api_router, root_router
from .db import async_session_maker, close_db
from .exceptions import DomainError
from .metrics import set_hmac_configured, setup_metrics
from .schemas import ERROR_CODES
from .services import payment as payment_service
from .services.webhook_security import webhook_hmac_configured
from .utils.logging import configure_logging, log_event, logger

configure_logging()


def _format_error_catalog() -> str:
    lines: list[str] = []
    for area, codes in ERROR_CODES.items():
        lines.append(f"\n### Erros — `{area}`\n")
        lines.append("| Codigo | Significado |")
        lines.append("|--------|-------------|")
        for code, desc in codes.items():
            lines.append(f"| `{code}` | {desc} |")
    return "\n".join(lines)


tags_metadata = [
    {
        "name": "config",
        "description": (
            "Onboarding em /api/v1: URL publica, URLs internas por categoria, API key Asaas "
            "e registro do webhook oficial."
        ),
    },
    {
        "name": "pixkey",
        "description": "Cadastro e validacao DICT de chaves Pix usadas como destino em payouts.",
    },
    {
        "name": "payment",
        "description": (
            "Payouts PIX (saida): kind=pixkey (transferencia por chave) ou kind=qrcode "
            "(pagamento de BR Code). Fila, agendamento, cancelamento, conciliacao."
        ),
    },
    {
        "name": "charge",
        "description": (
            "Cobrancas PIX (entrada): kind=charge. Retorna BR Code + QR Code base64; "
            "PAYMENT_RECEIVED do Asaas marca como PAID."
        ),
    },
    {
        "name": "asaas-inbound",
        "description": "Endpoints chamados pelo Asaas (webhook + Mecanismo de Seguranca). Header asaas-access-token.",
    },
]

_DESCRIPTION = """
Middleware FastAPI sobre a API Asaas v3. Suporta dois fluxos:

- **Payouts (saida)** — `kind=pixkey | qrcode` — transferencia por chave PIX cadastrada
  ou pagamento de BR Code copia-e-cola.
- **Charges (entrada)** — `kind=charge` — cobrancas PIX recebidas via Asaas `/payments`
  com `billingType=PIX`, retornando BR Code + QR Code base64.

Aceita chaves de **producao** (`$aact_prod_*`) por padrao e **sandbox** (`$aact_hmlg_*`)
quando `ASAAS_ALLOW_SANDBOX=true`.

## Fluxo de configuracao

1. `POST /api/v1/config/url` → acesse a `verify_url` retornada para confirmar o dominio
2. `POST /api/v1/config/internal` (uma vez por categoria) → 3 URLs internas:
   - `target=scheduling` — agendamento (SCHEDULED, QUEUED)
   - `target=payout`     — status de payouts (kind=pixkey/qrcode)
   - `target=charge`     — status de cobrancas (kind=charge)
   - `target=default`    — catch-all legado (usado como fallback)
3. `POST /api/v1/config/key` → valida API key e retorna `security_token` + instrucoes
4. (Opcional, p/ Mecanismo de Seguranca) cola o token + URL validadora no painel Asaas
5. `POST /api/v1/config/key/confirm` → registra o webhook oficial em `<external_url>/webhook/`

## Maquinas de estados

**Payouts (kind=pixkey | qrcode):**
```
SCHEDULED → QUEUED → SUBMITTING → SUBMITTED → PAID
                 ↘ AWAITING_BALANCE ↗         ↘ FAILED
                                               ↘ CANCELLED
```

**Charges (kind=charge):**
```
PENDING ─── PAYMENT_CONFIRMED|PAYMENT_RECEIVED ───► PAID
   │
   ├── PAYMENT_OVERDUE ──────────────────────────► EXPIRED
   ├── DELETE /charge | PAYMENT_DELETED ─────────► CANCELLED
   └── PAYMENT_REFUNDED (apos PAID) ─────────────► REFUNDED
```

## Regras de QR Code (payouts)

- QR com valor fixo (tag 54) nao aceita `amount` diferente
- QR sem valor fixo exige `amount` no corpo
- QR dinamico **nao pode ser agendado**
- Use `POST /api/v1/payment/qrcode/analyze` para inspecionar um BR Code antes de pagar

## Find-or-create de customer (charges)

`POST /api/v1/charge/pix` exige `external_id` (do pagador) e:
- Se o `external_id` ja tem customer cadastrado localmente → reusa
- Se nao → `payer` (name, cpf_cnpj, email?, phone?) e **obrigatorio** para criar
- Asaas e consultado por `externalReference` antes de criar (resiliente a wipe local)

## Formato de erros

Todos os erros de dominio vem como `HTTP 4xx/5xx` com corpo:

```json
{"detail": "<codigo>"}
```

Quando o codigo tem contexto dinamico, ele vem como prefixo + `:` + detalhe —
ex: `holder_mismatch: expected 074... got 123...`.

## Notificacoes internas — 3 destinos

A cada transicao de status, o asaas-app envia `POST` ao destino apropriado:

| Evento | Destino | Configurar com target= |
|---|---|---|
| kind=charge (PENDING, PAID, EXPIRED, CANCELLED, REFUNDED) | `internal_url_charge` | `charge` |
| kind=pixkey/qrcode com status SCHEDULED ou QUEUED | `internal_url_scheduling` | `scheduling` |
| kind=pixkey/qrcode com status SUBMITTED, PAID, FAILED, AWAITING_BALANCE, CANCELLED | `internal_url_payout` | `payout` |

Fallback: se o destino especifico nao esta setado, cai em `internal_url` (catch-all legado).

Payload comum:

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "kind": "pixkey" | "qrcode" | "charge",
  "external_id": "ID do pagador (charge) ou da pixkey (pixkey) ou null (qrcode)",
  "status": "PAID"
}
```

`AWAITING_BALANCE` so dispara na primeira transicao (suprimido em retries do worker).

## Catalogo de erros
""" + _format_error_catalog()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log_event("service.startup")

    # Bootstrap config a partir do .env — pos-wipe, isso re-hidrata
    # asaas.config sem precisar de POST /api/v1/config/key manual.
    # DB vence se ja tem entry; env so preenche o que falta.
    async with async_session_maker() as session:
        try:
            seed_result = await cfg.seed_from_env(session)
            await session.commit()
            log_event("config.seed_from_env", result=seed_result)
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            log_event("config.seed_from_env.failed", error=str(exc))

    # ── Startup security check: alerta se HMAC estiver desabilitado ──
    async with async_session_maker() as session:
        hmac_ok = await webhook_hmac_configured(session)
    if not hmac_ok:
        logger.critical(
            "webhook_hmac_disabled_at_startup",
            service="asaas",
            msg=(
                "ASAAS_WEBHOOK_SECRET nao configurado em producao! "
                "Webhooks estao aceitando chamadas sem validar assinatura HMAC. "
                "Configure a env ASAAS_WEBHOOK_SECRET ou cadastre o secret via "
                "config store (K_ASAAS_WEBHOOK_SECRET)."
            ),
        )
        log_event("webhook_hmac_disabled_at_startup", severity="CRITICAL")
    set_hmac_configured(hmac_ok)

    worker = asyncio.create_task(payment_service.worker_loop(30.0))
    try:
        yield
    finally:
        worker.cancel()
        log_event("service.shutdown")
        await close_db()


app = FastAPI(
    title="asaas-app",
    version="0.1.0",
    description=_DESCRIPTION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Converte excecoes de dominio em respostas HTTP padronizadas."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


app.include_router(api_router)
app.include_router(root_router)
setup_metrics(app)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"app": "asaas-app", "status": "up", "version": app.version}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")
