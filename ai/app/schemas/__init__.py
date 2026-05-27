"""Schemas Pydantic para o servico AI.

CONVENTION §2 exige Pydantic 2.8+.

Cada dominio de endpoint tem seu proprio arquivo de schema:
  - text.py       — endpoints /text/ (DeepSeek generativa)
  - image.py      — endpoints /image/ (Gemini geracao/vision)
  - ocr.py        — endpoints /ocr/ (Google Cloud Vision)
  - tts.py        — endpoints /tts/ (ElevenLabs)
  - json_endpoint.py — endpoints /json/ (DeepSeek JSON mode)
  - v1.py         — endpoints /v1/ (envelope padrao + chat/summarize/extract)
"""

from app.schemas.text import TextRequest, TextResponse
from app.schemas.image import ImageRequest, ImageResponse, VisionRequest, VisionResponse
from app.schemas.ocr import OCRResponse
from app.schemas.tts import TTSRequest, TTSResponse
from app.schemas.json_endpoint import JSONRequest, JSONResponse
from app.schemas.v1 import (
    APIResponse,
    ChatData,
    ChatMessage,
    ChatRequest,
    ExtractData,
    ExtractRequest,
    SummarizeData,
    SummarizeFormat,
    SummarizeRequest,
    UsageStats,
)

__all__ = [
    "TextRequest",
    "TextResponse",
    "ImageRequest",
    "ImageResponse",
    "VisionRequest",
    "VisionResponse",
    "OCRResponse",
    "TTSRequest",
    "TTSResponse",
    "JSONRequest",
    "JSONResponse",
    "APIResponse",
    "ChatData",
    "ChatMessage",
    "ChatRequest",
    "ExtractData",
    "ExtractRequest",
    "SummarizeData",
    "SummarizeFormat",
    "SummarizeRequest",
    "UsageStats",
]
