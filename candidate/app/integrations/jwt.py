from app.integrations import BaseClient, request_with_retry


class JwtClient(BaseClient):
    """POST /api/v1/tokens/refresh — renova tokens"""

    async def refresh_token(self, refresh_token: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/tokens/refresh",
            json={"refresh_token": refresh_token},
        )
        return resp.json()
