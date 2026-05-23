"""Schemas para perfis de WhatsApp."""

from pydantic import BaseModel, Field


class WhatsAppProfile(BaseModel):
    external_id: str = Field(description="ID do contacto no notify")
    phone: str = Field(description="Numero de WhatsApp (com 55)")
    name: str = Field(default="", description="Nome do perfil")
    is_business: bool = Field(default=False, description="Conta comercial?")
    has_picture: bool = Field(default=False, description="Tem foto de perfil?")
    picture: str = Field(default="", description="URL da foto de perfil")
    status: str = Field(default="", description="Recado/status do WhatsApp")
    description: str = Field(default="", description="Descricao do perfil")
    website: str = Field(default="", description="Site (primeiro se multiplos)")
    email: str = Field(default="", description="Email comercial")
    address: str = Field(default="", description="Endereco comercial")
    category: str = Field(default="", description="Categoria do negocio")
    business_hours: str = Field(default="", description="Horario comercial (timezone)")
    error: str = Field(default="", description="Mensagem de erro se falhou")


class WhatsAppProfileList(BaseModel):
    count: int = Field(description="Total de perfis retornados")
    items: list[WhatsAppProfile] = Field(description="Lista de perfis")
