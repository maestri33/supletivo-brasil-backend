"""Cliente CPFHub.io — consulta de dados cadastrais via CPF.

API externa (https://api.cpfhub.io). Autenticacao via header x-api-key.
Chamadas sao server-side ONLY — a key nunca sai do backend.

Resposta sempre envelopada em {success, data, error}. Verificar `success`
antes de consumir `data`.
"""

import re

from pydantic import BaseModel, ConfigDict, Field

from app.integrations import BaseClient, IntegrationError, request_with_retry

CPF_CLEAN = re.compile(r"[.\-/ ]")


def _strip_cpf(cpf: str) -> str:
    """Remove formatacao do CPF (pontos, traco, espacos, barras)."""
    return CPF_CLEAN.sub("", cpf)


class CPFHubData(BaseModel):
    """Dados cadastrais retornados em caso de sucesso."""

    model_config = ConfigDict(extra="ignore")

    cpf: str
    name: str
    name_upper: str = Field(alias="nameUpper")
    gender: str  # "M" | "F"
    birth_date: str = Field(alias="birthDate")  # "DD/MM/AAAA"
    day: int
    month: int
    year: int


class CPFHubError(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str


class CPFHubResponse(BaseModel):
    """Envelope completo da API CPFHub."""

    model_config = ConfigDict(extra="ignore")
    success: bool
    data: CPFHubData | None = None
    error: CPFHubError | None = None


class CPFHubClient(BaseClient):
    """GET /cpf/{cpf} — consulta dados cadastrais de um CPF.

    Uso:
        async with httpx.AsyncClient(
            base_url=settings.CPFHUB_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
            headers={"x-api-key": settings.CPFHUB_API_KEY},
        ) as http:
            client = CPFHubClient(http)
            data = await client.lookup("12345678900")
    """

    async def lookup(self, cpf: str) -> CPFHubData:
        """Consulta CPF e retorna dados cadastrais.

        Raises:
            IntegrationError: CPF invalido (400), nao encontrado (404),
                              rate limit (429), ou erro de servidor (500/503).
            httpx.HTTPStatusError: API key invalida (401).
        """
        clean = _strip_cpf(cpf)
        resp = await request_with_retry(
            self.client,
            "GET",
            f"/cpf/{clean}",
            max_retries=2,  # API externa — 2 retries bastam
        )
        body = resp.json()
        parsed = CPFHubResponse(**body)

        if not parsed.success:
            error_msg = parsed.error.message if parsed.error else "erro desconhecido"
            self.log.warning("cpfhub_lookup_failed", cpf=clean, error=error_msg)
            raise IntegrationError(f"CPFHub: {error_msg}")

        assert parsed.data is not None  # success=True garante data presente
        self.log.info(
            "cpfhub_lookup_ok",
            cpf=clean,
            name=parsed.data.name,
            gender=parsed.data.gender,
            birth_date=parsed.data.birth_date,
        )
        return parsed.data
