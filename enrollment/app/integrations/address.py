"""Integração com o serviço `address` (CEP + endereço por entidade).

O endereço da matrícula é vinculado ao tipo `enrollment` (o usuário neste
ponto já é `enrollment`, não mais `lead`). Espelha o contrato usado pelo
candidate (entity_type = "lead" lá), só muda a string.
"""

from app.integrations import BaseClient, request_with_retry


class AddressClient(BaseClient):
    """POST  /api/v1/addresses                                — cria endereço
    GET   /api/v1/addresses/cep/{cep}                       — consulta CEP
    GET   /api/v1/entities/{type}/{ext_id}                  — endereço da entidade
    POST  /api/v1/entities/{type}/{ext_id}/cep              — vincula por CEP."""

    async def create_address(self, **fields) -> dict:
        resp = await request_with_retry(self.client, "POST", "/api/v1/addresses", json=fields)
        return resp.json()

    async def check_cep(self, cep: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/addresses/cep/{cep}")
        return resp.json()

    async def get_entity_address(self, entity_type: str, external_id: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "GET",
            f"/api/v1/entities/{entity_type}/{external_id}",
        )
        return resp.json()

    async def update_entity_cep(self, entity_type: str, external_id: str, cep: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            f"/api/v1/entities/{entity_type}/{external_id}/cep",
            params={"cep": cep},
        )
        return resp.json()
