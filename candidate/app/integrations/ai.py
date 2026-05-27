"""Integracao com o servico `ai` (CONVENTION §13: IA centralizada no app `ai`).

Usado para descrever a selfie (Gemini Vision) e validar heuristicamente que ha'
uma pessoa real na imagem. O `ai` baixa a imagem da URL informada server-side.
"""

from app.integrations import BaseClient, request_with_retry


class AIClient(BaseClient):
    """POST /api/v1/image/vision — descreve uma imagem ({image_url} -> {description})"""

    async def vision(self, image_url: str) -> str:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/image/vision",
            json={"image_url": image_url},
        )
        return resp.json().get("description", "")
