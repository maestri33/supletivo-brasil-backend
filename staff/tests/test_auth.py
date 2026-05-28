"""Testes do gate de autenticacao JWT+role (milestone 1).

Testa gates de rejeicao:
- sem token → 401 (HTTPBearer default, antes do JWKS)
- token + JWKS offline → 502 (httpx nao alcanca o servidor JWKS)
- token valido + role errada → 403 (quando JWKS disponivel — fixture futura)

Caminho feliz coberto quando houver fixture de JWT com JWKS real.
"""

from httpx import AsyncClient


async def test_me_no_token(client: AsyncClient) -> None:
    """Sem header Authorization → HTTPBearer retorna 401."""
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401


async def test_me_jwks_unreachable(client: AsyncClient) -> None:
    """Token presente mas JWKS offline → 502 (gateway error)."""
    resp = await client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert resp.status_code == 502
