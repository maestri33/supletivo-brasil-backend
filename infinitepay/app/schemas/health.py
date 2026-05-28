from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    webhook_security: dict | None = None
