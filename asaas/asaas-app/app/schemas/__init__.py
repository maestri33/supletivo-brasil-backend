"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ───────────────────────────── shared ─────────────────────────────


class OkResponse(BaseModel):
    ok: bool = True

    model_config = ConfigDict(json_schema_extra={"example": {"ok": True}})


class ErrorResponse(BaseModel):
    """Erro de dominio. Sempre um JSON com campo `detail` contendo um codigo curto.

    Consulte a lista completa em `ERROR_CODES` na descricao da API.
    """

    detail: str = Field(
        ..., description="Codigo de erro ou mensagem. Para 400, um dos codigos documentados."
    )

    model_config = ConfigDict(json_schema_extra={"example": {"detail": "pixkey_not_found"}})


# ───────────────────────── error catalog ──────────────────────────
# Usado por rotas via responses= para documentar no OpenAPI e pelo README.
# Agrupado por area. Mensagens dinamicas (com :detail) aparecem com prefix.

ERROR_CODES: dict[str, dict[str, str]] = {
    "config": {
        "external_url_not_set": "Nenhuma URL publica registrada. Execute POST /api/v1/config/url.",
        "nonce_not_found": "Nonce invalido ou ja consumido.",
        "nonce_already_used": "Nonce ja consumido; gere outro em /api/v1/config/url.",
        "nonce_expired": "Nonce expirou (TTL 600s); gere outro.",
        "production_key_required": (
            "API key precisa comecar com $aact_prod_ (ou $aact_hmlg_ se ASAAS_ALLOW_SANDBOX=true)."
        ),
        "asaas_rejected_key": "Asaas recusou a chave; veja o sufixo :detail.",
        "set_key_not_done": "Chamou /api/v1/config/key/confirm antes de /api/v1/config/key.",
        "onboarding_send_failed": "URL interna nao respondeu (network error).",
        "onboarding_http_<code>": "URL interna respondeu non-2xx ao receber o doc de onboarding.",
        "asaas_error": "Falha upstream no Asaas (502); veja o sufixo.",
        "invalid_internal_url_target": (
            "target deve ser default | scheduling | payout | charge; veja o sufixo."
        ),
    },
    "pixkey": {
        "asaas_api_key_not_set": "Rode POST /api/v1/config/key primeiro.",
        "external_id_required": "external_id nao pode ser vazio.",
        "external_id_already_exists": "Ja existe pixkey com esse external_id.",
        "pix_key_already_registered": "Essa chave Pix ja esta cadastrada (em outro external_id).",
        "invalid_key_type": "Use CPF, CNPJ, EMAIL, PHONE ou EVP.",
        "invalid_document_length": "CPF precisa de 11 digitos, CNPJ de 14.",
        "invalid_cpf_format": "CPF fora do padrao 11 digitos.",
        "invalid_cnpj_format": "CNPJ fora do padrao 14 digitos.",
        "invalid_email_format": "Email fora do RFC 5322 simplificado.",
        "invalid_phone_format_expected_+55DDDNNNNNNNNN": "Telefone precisa vir como +55 DDD + numero.",  # noqa: E501
        "invalid_evp_format": "EVP precisa ser um UUID valido.",
        "holder_mismatch": "CPF/CNPJ do titular no DICT nao bate com o esperado; veja o sufixo.",
        "dict_lookup_failed": "Asaas rejeitou o lookup DICT; veja o sufixo.",
        "not_found": "Pixkey nao encontrada (404).",
    },
    "payment": {
        "pixkey_not_found": (
            "O external_id informado nao existe — cadastre em POST /api/v1/pixkey."
        ),
        "invalid_amount": "amount deve ser numero positivo.",
        "invalid_date": "Data fora do formato YYYY-MM-DD; veja o sufixo.",
        "payment_id_already_exists": "Ja existe payment com esse payment_id (idempotencia).",
        "invalid_qrcode_payload": "BR Code nao foi parseado como TLV valido.",
        "qrcode_amount_required": "Esse QR nao tem valor fixo; envie amount.",
        "qrcode_fixed_amount_mismatch": "Esse QR tem valor fixo diferente; veja o sufixo.",
        "dynamic_qrcode_scheduling_not_supported": "QR dinamico nao pode ser agendado (pode expirar).",  # noqa: E501
        "cannot_cancel_status": "Status atual nao permite cancelar; veja o sufixo.",
        "asaas_cancel_failed": "Asaas rejeitou o cancelamento; veja o sufixo.",
        "invalid_kind": "kind deve ser pixkey, qrcode ou charge; veja o sufixo.",
        "invalid_status": "status informado nao e valido; veja o sufixo.",
        "cannot_delete_status": "So e possivel deletar payments SCHEDULED ou AWAITING_BALANCE.",
        "not_found": "Payment nao encontrado (404).",
    },
    "charge": {
        "customer_required": (
            "external_id nao registrado; envie payer (name, cpf_cnpj) para criar customer."
        ),
        "invalid_cpf_cnpj": "cpf_cnpj deve ter 11 (CPF) ou 14 (CNPJ) digitos.",
        "invalid_due_date": "due_date fora do formato YYYY-MM-DD ou no passado; veja o sufixo.",
        "asaas_customer_create_failed": "Asaas rejeitou criar customer; veja o sufixo.",
        "asaas_charge_create_failed": "Asaas rejeitou criar cobranca; veja o sufixo.",
        "asaas_charge_delete_failed": "Asaas rejeitou cancelar cobranca; veja o sufixo.",
        "asaas_qr_fetch_failed": "Asaas falhou ao retornar QR Code; veja o sufixo.",
        "cannot_cancel_status": (
            "Cobranca em status terminal nao pode ser cancelada; veja o sufixo."
        ),
        "not_found": "Cobranca nao encontrada (404).",
    },
    "webhook": {
        "invalid_token": "Header asaas-access-token ausente ou incorreto (401).",
    },
}


def _error_example(code: str) -> dict:
    return {"detail": code}


def responses_for(*codes: str, status_map: dict[int, list[str]] | None = None) -> dict:
    """Constroi o dict `responses=` para uma rota FastAPI.

    Uso:
        @router.post(..., responses=responses_for("pixkey_not_found", "invalid_amount"))
        # agrupa todos em 400 com examples nomeados por codigo

    Ou explicitamente:
        responses_for(status_map={400: ["invalid_amount"], 404: ["not_found"]})
    """
    if status_map is None:
        status_map = {400: list(codes)}
    result: dict[int, dict] = {}
    for status, errs in status_map.items():
        if not errs:
            continue
        result[status] = {
            "model": ErrorResponse,
            "description": "; ".join(errs),
            "content": {
                "application/json": {
                    "examples": {
                        code: {"summary": code, "value": _error_example(code)} for code in errs
                    },
                }
            },
        }
    return result


# ───────────────────────────── pixkey ─────────────────────────────


class PixKeyResponse(BaseModel):
    """Chave Pix cadastrada e validada no DICT."""

    external_id: str = Field(..., description="ID do destinatario no sistema cliente")
    key: str = Field(..., description="Chave Pix")
    key_type: str = Field(..., description="CPF | CNPJ | EMAIL | PHONE | EVP")
    holder_document: str = Field(
        ..., description="CPF (11 digitos) ou CNPJ (14 digitos) do titular"
    )
    holder_name: str | None = Field(default=None, description="Nome do titular retornado pelo DICT")
    bank_name: str | None = Field(default=None, description="Nome do banco do titular")
    validated_at: str | None = Field(
        default=None, description="Timestamp ISO 8601 da validacao DICT"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "diandra_celular",
                "key": "+5542998171770",
                "key_type": "PHONE",
                "holder_document": "07461638947",
                "holder_name": "Diandra S.",
                "bank_name": "SICOOB",
                "validated_at": "2026-04-24T17:30:00",
            }
        }
    )


class PixKeyCheckResponse(BaseModel):
    """Resultado de consulta de chave Pix (com ou sem persistencia)."""

    source: str = Field(
        ..., description='"db" se ja cadastrada localmente, "dict" se consultada ao vivo no DICT'
    )
    data: dict[str, Any] = Field(
        ..., description="Dados do titular. Campos identicos a PixKeyResponse quando source=db."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "dict",
                "data": {
                    "key": "+5542998171770",
                    "holder_document": "074.***.**9-47",
                    "holder_name": "Diandra S.",
                    "bank_name": "SICOOB",
                },
            }
        }
    )


# ───────────────────────────── payment ────────────────────────────


class PaymentResponse(BaseModel):
    """Pagamento Pix criado ou consultado."""

    payment_id: str = Field(
        ..., description="ID idempotente do pagamento (gerado ou fornecido pelo cliente)"
    )
    kind: str = Field(..., description='"pixkey" | "qrcode"')
    external_id: str | None = Field(default=None, description="external_id da pixkey (kind=pixkey)")
    qrcode_payload: str | None = Field(
        default=None, description="BR Code copia-e-cola (kind=qrcode)"
    )
    amount: float = Field(..., description="Valor em BRL")
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")
    scheduled_for: str | None = Field(
        default=None,
        description="Datetime ISO 8601 UTC do disparo agendado. Null para pagamentos imediatos.",
    )
    status: str = Field(
        ...,
        description=(
            "SCHEDULED → QUEUED → SUBMITTING → SUBMITTED → "
            "PAID | FAILED | CANCELLED | AWAITING_BALANCE"
        ),
    )
    asaas_id: str | None = Field(
        default=None, description="UUID da transferencia/transacao no Asaas"
    )
    last_error: str | None = Field(
        default=None, description="Ultimo erro registrado (ex: insufficient_balance)"
    )
    created_at: str | None = Field(default=None, description="Timestamp ISO 8601 de criacao")
    updated_at: str | None = Field(
        default=None, description="Timestamp ISO 8601 da ultima atualizacao"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_id": "diandra_salario_202604",
                "kind": "pixkey",
                "external_id": "diandra_celular",
                "qrcode_payload": None,
                "amount": 0.03,
                "description": "Pagamento salario abril/2026",
                "scheduled_for": None,
                "status": "PAID",
                "asaas_id": "bc46e593-0a72-4495-a2f8-b4ad499791c0",
                "last_error": None,
                "created_at": "2026-04-24T17:35:24",
                "updated_at": "2026-04-24T17:35:36",
            }
        }
    )


# ───────────────────────────── qrcode ─────────────────────────────


class QRCodeAnalyzeResponse(BaseModel):
    """Analise TLV de um BR Code PIX sem efetuar pagamento."""

    valid_tlv: bool = Field(..., description="True se o payload foi parseado como TLV valido")
    kind: str = Field(..., description='"static" ou "dynamic"')
    point_of_initiation_method: str | None = Field(
        default=None, description="Tag 01: 11=estatico reutilizavel, 12=uso unico"
    )
    amount: float | None = Field(
        default=None, description="Valor fixo (tag 54) ou null se variavel"
    )
    allows_amount_edit: bool = Field(
        ..., description="True quando o QR nao tem valor fixo e aceita amount customizado"
    )
    can_schedule: bool = Field(
        ..., description="True para QR estatico; False para QR dinamico (nao pode agendar)"
    )
    pix_key: str | None = Field(default=None, description="Chave Pix embutida (apenas QR estatico)")
    dynamic_url: str | None = Field(
        default=None, description="URL de payload dinamico (apenas QR dinamico)"
    )
    merchant_name: str | None = Field(default=None, description="Nome do recebedor (tag 59)")
    merchant_city: str | None = Field(default=None, description="Cidade do recebedor (tag 60)")
    reference: str | None = Field(
        default=None, description="Referencia adicional (tag 62, subtag 05)"
    )
    has_crc: bool = Field(..., description="True se o CRC16 (tag 63) esta presente no payload")
    warnings: list[str] = Field(
        default_factory=list,
        description="Avisos: amount_not_fixed, dynamic_qrcode_may_expire, etc.",
    )
    raw_fields: dict[str, str] = Field(
        default_factory=dict, description="Todos os campos TLV raiz extraidos (tag -> valor)"
    )
    merchant_account_fields: dict[str, str] = Field(
        default_factory=dict, description="Subtags da Merchant Account Information (tag 26)"
    )
    additional_data_fields: dict[str, str] = Field(
        default_factory=dict, description="Subtags de Additional Data Field Template (tag 62)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid_tlv": True,
                "kind": "static",
                "point_of_initiation_method": "11",
                "amount": 0.03,
                "allows_amount_edit": False,
                "can_schedule": True,
                "pix_key": "+5542998171770",
                "dynamic_url": None,
                "merchant_name": "Diandra S",
                "merchant_city": "GUARAPUAVA",
                "reference": None,
                "has_crc": True,
                "warnings": [],
                "raw_fields": {
                    "00": "01",
                    "01": "11",
                    "26": "...",
                    "52": "0000",
                    "53": "986",
                    "54": "0.03",
                    "58": "BR",
                    "59": "Diandra S",
                    "60": "GUARAPUAVA",
                    "63": "ABCD",
                },
                "merchant_account_fields": {"00": "br.gov.bcb.pix", "01": "+5542998171770"},
                "additional_data_fields": {},
            }
        }
    )


# ───────────────────────────── config ─────────────────────────────


class SetUrlRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description=(
            "URL publica base do asaas-app. O webhook Asaas sera registrado em <url>/webhook/."
        ),
    )

    model_config = ConfigDict(json_schema_extra={"example": {"url": "https://asaas.v7m.net/"}})


class SetUrlResponse(BaseModel):
    verify_url: HttpUrl = Field(
        ..., description="URL que deve ser acessada para confirmar o dominio"
    )
    nonce: str = Field(..., description="Token de uso unico embutido na verify_url")
    expires_in: int = Field(..., description="TTL do nonce em segundos")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verify_url": "https://asaas.v7m.net/api/v1/config/url/verify/abc123xyz",
                "nonce": "abc123xyz",
                "expires_in": 300,
            }
        }
    )


class SetInternalUrlRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description=(
            "URL do sistema interno que recebera copias dos eventos Asaas e eventos sinteticos."
        ),
    )
    target: str = Field(
        default="default",
        description=(
            "Categoria do evento que sera roteado a esta URL. "
            "default = catch-all (compat); scheduling = transicoes de agendamento; "
            "payout = status de payouts PIX (pixkey, qrcode); "
            "charge = status de cobrancas PIX recebidas."
        ),
        pattern="^(default|scheduling|payout|charge)$",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"url": "http://127.0.0.1:8081/charge", "target": "charge"}}
    )


class ConfigInternalResponse(BaseModel):
    ok: bool = Field(..., description="True se o onboarding foi entregue e a URL salva")
    internal_url: str = Field(..., description="URL interna salva")
    target: str = Field(..., description="Categoria associada (default|scheduling|payout|charge)")
    onboarding_status: int = Field(
        ..., description="HTTP status code retornado pelo sistema interno"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "internal_url": "http://127.0.0.1:8081/charge",
                "target": "charge",
                "onboarding_status": 200,
            }
        }
    )


class SetKeyRequest(BaseModel):
    api_key: str = Field(
        ...,
        min_length=20,
        description="API key Asaas de producao ($aact_prod_*). Chaves sandbox sao rejeitadas.",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"api_key": "$aact_prod_xxxxxxxxxxxxxxxxxxxxx"}}
    )


class SetKeyResponse(BaseModel):
    security_token: str = Field(..., description="Token para colar no Mecanismo de Seguranca Asaas")
    security_validator_url: HttpUrl = Field(
        ..., description="URL validadora para colar no Mecanismo de Seguranca Asaas"
    )
    webhook_endpoint: HttpUrl = Field(
        ..., description="URL que sera registrada como webhook Asaas em /api/v1/config/key/confirm"
    )
    events: list[str] = Field(..., description="Eventos Asaas assinados pelo webhook gerenciado")
    account: dict[str, Any] = Field(..., description="Resumo da conta retornado por /v3/myAccount")
    instructions_html: str = Field(
        ..., description="Instrucoes HTML prontas para exibir ao operador"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "security_token": "a1b2c3d4e5f6...",
                "security_validator_url": "https://asaas.v7m.net/security-validator",
                "webhook_endpoint": "https://asaas.v7m.net/webhook/",
                "events": [
                    "TRANSFER_CREATED",
                    "TRANSFER_DONE",
                    "TRANSFER_FAILED",
                    "PIX_TRANSACTION_CREATED",
                    "PIX_TRANSACTION_COMPLETED",
                    "PIX_TRANSACTION_CANCELLED",
                ],
                "account": {"name": "Empresa Ltda", "email": "api@empresa.com"},
                "instructions_html": "<ol>...</ol>",
            }
        }
    )


class ConfigConfirmResponse(BaseModel):
    ok: bool = Field(..., description="True se o webhook foi criado/recriado com sucesso")
    webhook_registered: dict[str, Any] = Field(
        ..., description="Objeto webhook retornado pelo Asaas"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "webhook_registered": {
                    "id": "8a3f2d1e-...",
                    "url": "https://asaas.v7m.net/webhook/",
                    "enabled": True,
                    "events": ["TRANSFER_DONE", "TRANSFER_FAILED"],
                },
            }
        }
    )


class InternalNotification(BaseModel):
    """Payload enviado ao webhook interno (internal_url_*) a cada transicao de status.

    Roteamento por target:
      - kind=charge                          -> internal_url_charge
      - kind in (pixkey, qrcode), status SCHEDULED/QUEUED -> internal_url_scheduling
      - kind in (pixkey, qrcode), demais     -> internal_url_payout
    Fallback: internal_url (legado catch-all) quando o target especifico nao esta setado.
    """

    payment_id: str = Field(..., description="ID do pagamento (pay_...)")
    kind: str = Field(..., description='"pixkey" | "qrcode" | "charge"')
    external_id: str | None = Field(
        default=None,
        description=(
            "external_id da pixkey (kind=pixkey) ou do customer (kind=charge). "
            "null para kind=qrcode."
        ),
    )
    status: str = Field(
        ...,
        description=(
            "Novo status. Outbound: SCHEDULED | QUEUED | SUBMITTED | PAID | etc. "
            "Charge: PENDING | PAID | EXPIRED | CANCELLED | REFUNDED."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example: pixkey": {
                "payment_id": "pay_a1b2c3d4e5f6a7b8",
                "kind": "pixkey",
                "external_id": "victor_celular",
                "status": "SUBMITTED",
            },
            "example: qrcode": {
                "payment_id": "pay_97584b93e49e4da4",
                "kind": "qrcode",
                "external_id": None,
                "status": "SCHEDULED",
            },
            "example: charge": {
                "payment_id": "pay_abc123",
                "kind": "charge",
                "external_id": "aluno_42",
                "status": "PAID",
            },
        }
    )


# ───────────────────────────── charge ─────────────────────────────


class CustomerInline(BaseModel):
    """Dados do pagador para criar customer no Asaas quando external_id e novo."""

    name: str = Field(..., min_length=1, description="Nome do pagador")
    cpf_cnpj: str = Field(..., description="CPF (11 digitos) ou CNPJ (14 digitos), so digitos")
    email: str | None = Field(default=None, description="Email do pagador")
    mobile_phone: str | None = Field(
        default=None,
        description="Telefone do pagador. Formato preferido +55DDDXXXXXXXXX.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Joao Pagador",
                "cpf_cnpj": "12345678901",
                "email": "joao@example.com",
                "mobile_phone": "+5543999999999",
            }
        }
    )


class ChargeCreateRequest(BaseModel):
    external_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Identificador do pagador (cliente). Find-or-create: se nao existir customer "
            "com esse external_id, payer e obrigatorio para cria-lo."
        ),
    )
    amount: float = Field(..., gt=0, description="Valor em BRL")
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")
    due_date: str | None = Field(
        default=None,
        description=(
            "YYYY-MM-DD. Quando a cobranca vence. "
            "Default = hoje + ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS dias."
        ),
    )
    payment_id: str | None = Field(
        default=None, description="ID idempotente opcional fornecido pelo cliente"
    )
    payer: CustomerInline | None = Field(
        default=None,
        description=(
            "Dados do pagador. Obrigatorio se external_id ainda nao tem customer registrado. "
            "Ignorado nas chamadas subsequentes (use endpoint /api/v1/customer para atualizar)."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "aluno_42",
                "amount": 250.00,
                "description": "Mensalidade junho/2026",
                "due_date": "2026-06-05",
                "payer": {
                    "name": "Maria Aluna",
                    "cpf_cnpj": "07426367980",
                    "email": "maria@example.com",
                },
            }
        }
    )


class ChargePixData(BaseModel):
    payload: str = Field(..., description="BR Code copia-e-cola (Pix)")
    encoded_image: str = Field(..., description="PNG base64 do QR Code")
    expiration_date: str | None = Field(
        default=None, description="ISO 8601 do vencimento do QR Code"
    )


class ChargeResponse(BaseModel):
    """Cobranca PIX criada ou consultada."""

    payment_id: str = Field(..., description="ID local (pay_...)")
    external_id: str = Field(..., description="external_id do customer (pagador)")
    amount: float = Field(..., description="Valor em BRL")
    description: str | None = Field(default=None)
    due_date: str | None = Field(default=None, description="YYYY-MM-DD")
    status: str = Field(..., description="PENDING | PAID | EXPIRED | CANCELLED | REFUNDED")
    asaas_id: str | None = Field(default=None, description="ID da cobranca no Asaas")
    pix: ChargePixData | None = Field(
        default=None, description="BR Code + QR Code (null se ainda nao buscado)"
    )
    last_error: str | None = Field(default=None)
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_id": "pay_a1b2c3d4e5f6a7b8",
                "external_id": "aluno_42",
                "amount": 250.00,
                "description": "Mensalidade junho/2026",
                "due_date": "2026-06-05",
                "status": "PENDING",
                "asaas_id": "pay_8120829379393283",
                "pix": {
                    "payload": "00020126360014br.gov.bcb.pix...",
                    "encoded_image": "iVBORw0KGgoAAAANSUhEUgA...",
                    "expiration_date": "2026-06-05T23:59:59",
                },
                "last_error": None,
                "created_at": "2026-05-15T16:00:00",
                "updated_at": "2026-05-15T16:00:00",
            }
        }
    )


class CustomerResponse(BaseModel):
    external_id: str
    asaas_id: str
    name: str
    cpf_cnpj: str
    email: str | None = None
    mobile_phone: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "aluno_42",
                "asaas_id": "cus_000005113863",
                "name": "Maria Aluna",
                "cpf_cnpj": "07426367980",
                "email": "maria@example.com",
                "mobile_phone": None,
                "created_at": "2026-05-15T15:50:00",
            }
        }
    )


class ConfigStatusResponse(BaseModel):
    configured: dict[str, Any] = Field(
        ..., description="Configuracoes salvas, com secrets mascarados"
    )
    account: dict[str, Any] | None = Field(default=None, description="Conta Asaas conectada")
    balance: dict[str, Any] | None = Field(default=None, description="Saldo Asaas atual")
    webhook_registered: dict[str, Any] | None = Field(
        default=None, description="Webhook gerenciado encontrado no Asaas"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Pendencias de configuracao ou falhas de consulta. Lista vazia = tudo ok.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "configured": {
                    "external_url": "https://asaas.v7m.net/",
                    "internal_url": "http://127.0.0.1:8081/",
                    "asaas_api_key": "$aact_prod_***",
                    "asaas_security_token": "a1b2***",
                },
                "account": {"name": "Empresa Ltda", "email": "api@empresa.com"},
                "balance": {"balance": 1234.56},
                "webhook_registered": {
                    "id": "8a3f2d1e-...",
                    "url": "https://asaas.v7m.net/webhook/",
                    "enabled": True,
                },
                "errors": [],
            }
        }
    )
