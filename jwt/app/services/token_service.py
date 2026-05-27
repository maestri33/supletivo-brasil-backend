"""Emissao, refresh e JWKS — usa config do .env, zero banco."""

import jwt

from app.config import get_settings, load_private_key, load_public_key
from app.exceptions import ValidationError
from app.services.jwt_service import (
    build_jwks_from_config,
    create_access_token_from_config,
    create_refresh_token_from_config,
    decode_token,
)
from app.stats import get_stats
from app.utils.logging import get_logger

log = get_logger(__name__)
settings = get_settings()
_PRIVATE_KEY = load_private_key(settings)
_PUBLIC_KEY = load_public_key(settings)


async def issue_token(external_id: str, roles: list[str]) -> dict:
    """Emite um par access + refresh token."""
    claims = {"external_id": external_id, "roles": roles}
    access_token = create_access_token_from_config(_PRIVATE_KEY, settings, claims)
    refresh_token = create_refresh_token_from_config(_PRIVATE_KEY, settings, claims)

    log.info(
        "token.emitido",
        external_id=external_id,
        roles=roles,
        alg=settings.jwt_algorithm,
        access_exp_min=settings.jwt_access_expire_minutes,
        refresh_exp_min=settings.jwt_refresh_expire_minutes,
    )
    get_stats().inc_issued()
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


async def refresh_token(refresh_token_str: str) -> dict:
    """Valida um refresh token e gera um novo par."""
    log.info("token.refresh.inicio")

    try:
        payload = jwt.decode(
            refresh_token_str,
            options={"verify_signature": False},
            algorithms=["RS256","RS384","RS512","HS256","HS384","HS512","ES256","ES384","ES512"],
        )
    except Exception:
        log.warning("token.refresh.payload_invalido")
        raise ValidationError("Refresh token invalido") from None

    if payload.get("type") != "refresh":
        log.warning("token.refresh.tipo_errado", tipo=payload.get("type"))
        raise ValidationError("Token nao e' do tipo refresh")

    # Valida assinatura com a chave publica
    try:
        decode_token(refresh_token_str, _PUBLIC_KEY, algorithms=[settings.jwt_algorithm])
    except Exception:
        log.warning("token.refresh.assinatura_invalida")
        raise ValidationError("Token nao foi emitido por este servidor") from None

    claims = {k: v for k, v in payload.items() if k not in ("iat", "exp", "type", "iss", "aud")}
    access_token = create_access_token_from_config(_PRIVATE_KEY, settings, claims)
    new_refresh_token = create_refresh_token_from_config(_PRIVATE_KEY, settings, claims)

    log.info("token.refresh.ok", external_id=claims.get("external_id"))
    get_stats().inc_refreshed()
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


async def get_jwks() -> dict:
    """Retorna chave publica no formato JWKS (RFC 7517)."""
    keys_dict = build_jwks_from_config(_PUBLIC_KEY, settings.jwt_algorithm)
    keys = keys_dict.get("keys", [])
    log.info("jwks.consultado", total_keys=len(keys))
    get_stats().inc_jwks()
    return {"keys": keys}
