from enum import Enum

from pydantic import BaseModel, Field


class SummarizeFormat(str, Enum):
    PARAGRAPH = "paragraph"
    BULLETS = "bullets"
    HEADLINE = "headline"


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    format: SummarizeFormat = Field(default=SummarizeFormat.PARAGRAPH)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None)


class SummarizeData(BaseModel):
    summary: str
