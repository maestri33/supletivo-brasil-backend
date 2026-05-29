"""Integração com o serviço `ai` (CONVENTION §14: IA centralizada no app `ai`).

Usado para validar heuristicamente a selfie (descrição vinda do Gemini Vision).
Falha do `ai` nunca bloqueia o funil — o caller decide o que fazer com erro.
"""

from app.integrations import BaseClient, request_with_retry


class AIClient(BaseClient):
    """POST /api/v1/image/vision — descreve uma imagem ({image_url} → {description})."""

    async def vision(self, image_url: str) -> str:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/image/vision",
            json={"image_url": image_url},
        )
        return resp.json().get("description", "")
