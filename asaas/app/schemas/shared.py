"""Shared schemas: base responses, error catalog, helper functions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
