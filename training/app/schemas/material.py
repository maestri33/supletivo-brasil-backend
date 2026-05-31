"""Schemas da Material (autoria: criar, atualizar, ler)."""

from datetime import datetime

from pydantic import Field

from app.schemas import APIModel


class MaterialCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    text_content: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)


class MaterialUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    text_content: str | None = Field(default=None, min_length=1)
    question: str | None = Field(default=None, min_length=1)
    expected_answer: str | None = Field(default=None, min_length=1)


class MaterialOut(APIModel):
    id: str
    title: str
    text_content: str
    question: str
    expected_answer: str
    has_video: bool
    has_photo: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m) -> "MaterialOut":
        """Monta a resposta a partir do model (deriva has_video/has_photo dos paths)."""
        return cls(
            id=str(m.id),
            title=m.title,
            text_content=m.text_content,
            question=m.question,
            expected_answer=m.expected_answer,
            has_video=m.video_path is not None,
            has_photo=m.photo_path is not None,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class MaterialListResponse(APIModel):
    total: int
    materials: list[MaterialOut]
