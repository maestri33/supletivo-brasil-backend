from app.integrations import BaseClient, request_with_retry


class AuthClient(BaseClient):
    """POST /api/v1/check — verifica CPF/phone e dispara OTP
    POST /api/v1/login — valida role + OTP, emite JWT
    POST /api/v1/register — registra novo usuario"""

    async def check(
        self,
        *,
        cpf: str | None = None,
        phone: str | None = None,
        external_id: str | None = None,
    ) -> dict:
        body = {k: v for k, v in {"cpf": cpf, "phone": phone, "external_id": external_id}.items() if v is not None}
        resp = await request_with_retry(self.client, "POST", "/api/v1/check", json=body)
        return resp.json()

    async def login(self, external_id: str, otp: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/login",
            json={"external_id": external_id, "otp": otp, "role": "lead"},
        )
        return resp.json()

    async def register(self, phone: str, cpf: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/register",
            json={"role": "lead", "phone": phone, "cpf": cpf},
        )
        return resp.json()
