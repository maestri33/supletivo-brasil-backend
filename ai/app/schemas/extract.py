from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)
    json_schema: dict = Field(
        description="JSON Schema que define a estrutura da extracao"
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None)


class ExtractData(BaseModel):
    extracted: dict
