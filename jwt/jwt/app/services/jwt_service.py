"""Operacoes de baixo nivel: encode, decode, JWKS."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def create_access_token_from_config(private_key: str, settings, claims: dict) -> str:
    """Assina um access token JWT."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_expire_minutes),
        "type": "access",
    }
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience

    return jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)


def create_refresh_token_from_config(private_key: str, settings, claims: dict) -> str:
    """Assina um refresh token JWT."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_refresh_expire_minutes),
        "type": "refresh",
    }
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer

    return jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, key: str, algorithms: list[str]) -> dict:
    """Decodifica e valida um token JWT (assinatura, exp, alg)."""
    return jwt.decode(token, key, algorithms=algorithms)


# ---------------------------------------------------------------------------
# JWKS
# ---------------------------------------------------------------------------

def _int_to_base64url(n: int) -> str:
    byte_length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


def build_jwks_from_config(public_key_str: str, algorithm: str) -> dict:
    """Monta representacao JWKS da chave publica."""
    if not algorithm.startswith("RS"):
        return {"keys": []}

    public_key = serialization.load_pem_public_key(
        public_key_str.encode(), backend=default_backend()
    )
    numbers = public_key.public_numbers()
    kid = hashlib.sha256(public_key_str.encode()).hexdigest()[:16]

    return {
        "keys": [{
            "kty": "RSA",
            "kid": kid,
            "n": _int_to_base64url(numbers.n),
            "e": _int_to_base64url(numbers.e),
            "alg": algorithm,
            "use": "sig",
        }]
    }
