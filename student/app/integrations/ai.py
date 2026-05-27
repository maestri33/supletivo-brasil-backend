"""Integracao com o app interno `ai` (CONVENTION §7, §14).

So' `ai` fala com provedor de IA (DeepSeek/Gemini/etc.). Aqui usamos a rota
POST /api/v1/image/vision para descrever uma foto e validar heuristicamente
que o documento e' do tipo esperado.
"""

from app.integrations import BaseClient, request_with_retry


class AIClient(BaseClient):
    """POST /api/v1/image/vision  ({image_url}) -> {description}"""

    async def vision(self, image_url: str) -> str:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/image/vision",
            json={"image_url": image_url},
        )
        return resp.json().get("description", "")
