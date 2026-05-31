from app.integrations import BaseClient, request_with_retry


class AddressClient(BaseClient):
    """Integracao com address-service.

    POST   /api/v1/addresses           — cria endereco
    GET    /api/v1/addresses/{id}      — busca endereco por id
    PATCH  /api/v1/addresses/{id}      — atualiza endereco
    DELETE /api/v1/addresses/{id}      — remove endereco
    GET    /api/v1/addresses/cep/{cep} — consulta CEP

    GET    /api/v1/entities/{type}/{ext_id}           — busca endereco da entidade
    POST   /api/v1/entities/{type}/{ext_id}/cep       — vincula por CEP
    POST   /api/v1/entities/{type}/{ext_id}/proof     — upload comprovante
    POST   /api/v1/entities/{type}/{ext_id}/unlink    — desvincula endereco
    """

    # ------------------------------------------------------------------
    # Addresses CRUD
    # ------------------------------------------------------------------

    async def create_address(self, **fields) -> dict:
        resp = await request_with_retry(self.client, "POST", "/api/v1/addresses", json=fields)
        return resp.json()

    async def get_address(self, address_id: int) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/addresses/{address_id}")
        return resp.json()

    async def update_address(self, address_id: int, **fields) -> dict:
        resp = await request_with_retry(
            self.client, "PATCH", f"/api/v1/addresses/{address_id}", json=fields
        )
        return resp.json()

    async def delete_address(self, address_id: int) -> None:
        await request_with_retry(self.client, "DELETE", f"/api/v1/addresses/{address_id}")

    # ------------------------------------------------------------------
    # CEP
    # ------------------------------------------------------------------

    async def check_cep(self, cep: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/addresses/cep/{cep}")
        return resp.json()

    # ------------------------------------------------------------------
    # Entity-address binding
    # ------------------------------------------------------------------

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

    async def upload_proof(
        self, entity_type: str, external_id: str, file_content: bytes, filename: str
    ) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            f"/api/v1/entities/{entity_type}/{external_id}/proof",
            files={"file": (filename, file_content, "application/octet-stream")},
        )
        return resp.json()

    async def unlink_address(self, entity_type: str, external_id: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            f"/api/v1/entities/{entity_type}/{external_id}/unlink",
        )
        return resp.json()
