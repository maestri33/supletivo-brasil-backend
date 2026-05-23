"""HTTP routes for the /config/* surface. Thin handlers — logic lives in services/."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..config import WEBHOOK_EVENTS, get_settings
from ..db import get_session
from ..exceptions import ValidationError
from ..schemas import (
    ConfigConfirmResponse,
    ConfigInternalResponse,
    ConfigStatusResponse,
    SetInternalUrlRequest,
    SetKeyRequest,
    SetKeyResponse,
    SetUrlRequest,
    SetUrlResponse,
    responses_for,
)
from ..services import config_internal, config_key, config_status, config_url

router = APIRouter(prefix="/config", tags=["config"])


# ---------- /config/url ----------


@router.post(
    "/url",
    response_model=SetUrlResponse,
    summary="Registrar URL publica",
    response_description="Nonce e URL de verificacao para provar que o dominio aponta para este app.",
)
def set_external_url(body: SetUrlRequest, db: Session = Depends(get_session)):
    """Cria um nonce temporario para validar a URL publica base do asaas-app."""
    nonce, verify_url = config_url.issue_nonce(db, str(body.url))
    db.commit()
    return SetUrlResponse(
        verify_url=verify_url, nonce=nonce, expires_in=get_settings().url_verify_nonce_ttl
    )


@router.get(
    "/url/verify/{nonce}",
    response_class=HTMLResponse,
    responses={400: {"description": "nonce_not_found | nonce_already_used | nonce_expired"}},
    summary="Validar URL publica",
    response_description="Pagina HTML simples confirmando se o nonce foi aceito.",
)
def verify_external_url(nonce: str, db: Session = Depends(get_session)):
    """Consome o nonce de `/config/url` e persiste a URL publica."""
    try:
        row = config_url.consume_nonce(db, nonce)
        db.commit()
        html = f"""<!doctype html><meta charset='utf-8'><title>URL verificada</title>
        <body style="font-family:system-ui;padding:32px;max-width:640px;margin:auto;">
        <h1>Pronto.</h1>
        <p>URL <b>{row.target_url}</b> registrada como <b>{row.purpose}</b>.</p>
        <p>Voce pode fechar esta aba.</p>
        </body>"""
        return HTMLResponse(html, status_code=200)
    except ValidationError as e:
        return HTMLResponse(
            f"<!doctype html><body style='font-family:system-ui;padding:32px'><h1>Falhou</h1><p>{e}</p></body>",
            status_code=400,
        )


# ---------- /config/internal ----------


@router.post(
    "/internal",
    response_model=ConfigInternalResponse,
    responses=responses_for(
        "onboarding_send_failed",
        "onboarding_http_<code>",
        "invalid_internal_url_target",
    ),
    summary="Registrar URL interna (por categoria)",
    response_description=(
        "URL salva apos receber com sucesso o documento de onboarding. "
        "Roteamento por target: default | scheduling | payout | charge."
    ),
)
def set_internal_url(body: SetInternalUrlRequest, db: Session = Depends(get_session)):
    """Envia onboarding ao destino interno e salva a URL na categoria escolhida.

    - target=default   -> internal_url (catch-all, compat)
    - target=scheduling-> internal_url_scheduling (eventos de agendamento)
    - target=payout    -> internal_url_payout (status de payouts PIX)
    - target=charge    -> internal_url_charge (status de cobrancas PIX recebidas)
    """
    url = str(body.url)
    try:
        key = cfg.internal_url_key(body.target)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"invalid_internal_url_target: {body.target}"
        ) from e
    try:
        result = config_internal.send_onboarding(url, target=body.target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"onboarding_send_failed: {e}") from e
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=f"onboarding_http_{result['status_code']}")
    cfg.set_(db, key, url)
    db.commit()
    return {
        "ok": True,
        "internal_url": url,
        "target": body.target,
        "onboarding_status": result["status_code"],
    }


# ---------- /config/key ----------


def _instructions_html(
    security_token: str,
    validator_url: str,
    webhook_endpoint: str,
    api_key: str,
) -> str:
    is_sandbox = api_key.startswith("$aact_hmlg_")
    env_label = "sandbox/homologacao" if is_sandbox else "producao"
    env_warn = (
        "<p><b>Ambiente sandbox:</b> operacoes nao movimentam dinheiro real.</p>"
        if is_sandbox
        else "<p><b>Ambiente producao:</b> este token autoriza operacoes reais.</p>"
    )
    panel_host = "sandbox.asaas.com" if is_sandbox else "asaas.com"
    return f"""
    <h3>Configuracao do Mecanismo de Seguranca Asaas ({env_label})</h3>
    {env_warn}
    <ol>
      <li>Entre no painel Asaas (<code>{panel_host}</code>) &rarr; Integracoes &rarr; Mecanismo de Seguranca.</li>
      <li>Cole este token: <code>{security_token}</code></li>
      <li>Cole esta URL validadora: <code>{validator_url}</code></li>
      <li>Habilite o mecanismo para autorizacao automatica de transferencias.</li>
    </ol>
    <p>Depois chame <code>POST /config/key/confirm</code>. O app registrara o webhook de eventos em
    <code>{webhook_endpoint}</code> com o mesmo authToken.</p>
    <p>Nao cadastre webhook na raiz do dominio; a URL exclusiva do Asaas e <code>/webhook/</code>.</p>
    """.strip()


@router.post(
    "/key",
    response_model=SetKeyResponse,
    responses=responses_for(
        "external_url_not_set", "production_key_required", "asaas_rejected_key"
    ),
    summary="Registrar API key Asaas",
    response_description="Token de seguranca, URL validadora, endpoint de webhook e instrucoes para o painel Asaas.",
)
def set_api_key(body: SetKeyRequest, db: Session = Depends(get_session)):
    """Valida uma API key de producao, salva segredo e gera instrucoes de configuracao manual."""
    external_url = cfg.get(db, cfg.K_EXTERNAL_URL)
    if not external_url:
        raise HTTPException(status_code=400, detail="external_url_not_set; call /config/url first")
    try:
        result = config_key.set_key(db, body.api_key)
    except ValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()

    validator_url = f"{external_url.rstrip('/')}/security-validator"
    webhook_endpoint = config_key.webhook_url(external_url)

    return SetKeyResponse(
        security_token=result["security_token"],
        security_validator_url=validator_url,
        webhook_endpoint=webhook_endpoint,
        events=WEBHOOK_EVENTS,
        account=result["account"],
        instructions_html=_instructions_html(
            result["security_token"], validator_url, webhook_endpoint, body.api_key
        ),
    )


@router.post(
    "/key/confirm",
    response_model=ConfigConfirmResponse,
    responses=responses_for(
        status_map={
            400: ["set_key_not_done", "external_url_not_set"],
            502: ["asaas_error"],
        }
    ),
    summary="Confirmar API key e recriar webhook",
    response_description="Webhook Asaas recriado em /webhook/ com authToken sincronizado.",
)
def confirm_api_key(db: Session = Depends(get_session)):
    """Registra ou recria o webhook oficial do Asaas apontando para `<external_url>/webhook/`."""
    try:
        result = config_key.confirm_key(db)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"asaas_error: {e}") from e
    return {"ok": True, "webhook_registered": result["webhook_registered"]}


# ---------- /config/status ----------


@router.get(
    "/status",
    response_model=ConfigStatusResponse,
    summary="Consultar status de configuracao",
    response_description="Conta, saldo, webhook registrado, configuracoes mascaradas e erros pendentes.",
)
def get_status(db: Session = Depends(get_session)):
    """Health operacional agregado. `errors: []` indica configuracao pronta."""
    return ConfigStatusResponse(**config_status.status(db))
