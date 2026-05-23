"""Endpoint de instrucoes — lista arquivos .md em /docs e serve conteudo."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/instructions", tags=["instructions"])

DOCS_DIR = Path("media/instructions")


class InstructionItem(BaseModel):
    name: str = Field(description="Nome do arquivo (slug sem .md)")
    filename: str = Field(description="Nome do arquivo .md")
    url: str = Field(description="URL via /media")


class InstructionList(BaseModel):
    count: int
    items: list[InstructionItem]


@router.get("", response_model=InstructionList, summary="Listar instrucoes")
async def list_instructions():
    """Lista todos os arquivos de instrucao (.md) disponiveis em /media/instructions/."""
    items: list[InstructionItem] = []
    if DOCS_DIR.exists():
        for f in sorted(DOCS_DIR.glob("*.md")):
            items.append(InstructionItem(
                name=f.stem,
                filename=f.name,
                url=f"/media/instructions/{f.name}",
            ))
    return InstructionList(count=len(items), items=items)
