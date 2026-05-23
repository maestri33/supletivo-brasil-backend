from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    service: str
