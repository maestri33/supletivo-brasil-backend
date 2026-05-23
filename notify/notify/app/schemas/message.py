"""Schemas Pydantic para Message."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import STATUS_PENDING


class MessageFlags(BaseModel):
    """Flags que controlam o pipeline de envio da mensagem.

    As flags atuam como modificadores do fluxo:
    - ai: DeepSeek reescreve o texto antes de enviar
    - tts: ElevenLabs gera audio e envia como nota de voz (so texto)
    - img: Gemini gera uma imagem e envia como midia

    img e tts sao mutuamente exclusivos — img vence.
    """

    tts: bool = Field(
        default=False,
        description="Gera audio via ElevenLabs e envia como nota de voz nativa (PTT). "
        "So funciona em mensagens de texto (ignorado se houver midia).",
    )
    ai: bool = Field(
        default=False,
        description="DeepSeek Pro reescreve o content da mensagem antes do envio",
    )
    img: bool = Field(
        default=False,
        description="Gemini gera uma imagem a partir de instruction (ou auto-prompt). "
        "Converte a mensagem para tipo 'media'.",
    )


class MessageSend(BaseModel):
    """Body para envio de mensagem multicanal (WhatsApp + Email)."""

    external_id: str = Field(
        description="ID do contacto destinatario (deve existir em /contacts)",
        examples=["victor-001"],
    )
    title: str | None = Field(
        default=None,
        description="Titulo da mensagem. Se nao informado, extraido do .md "
        "(primeiro # Titulo) ou 'Nova mensagem'. "
        "Usado como assunto do email e prefixo no WhatsApp",
        examples=["Verificacao de conta"],
    )
    content: str = Field(
        description="Texto da mensagem, URL de .md (download + extracao), "
        "ou prompt para IA se flags.ai=True",
        examples=["Ola! Sua entrega chegou."],
    )
    template_slug: str | None = Field(
        default=None,
        description="Slug do template de email a usar (ex: 'welcome', 'checkout', 'receipt'). "
        "Se nao informado ou nao encontrado, cai no 'default'.",
        examples=["welcome"],
    )
    media_url: str | None = Field(
        default=None,
        description="URL publica ou data URI base64 (data:image/png;base64,...) de midia anexa. "
        "Formatos: imagem, video, audio, documento.",
        examples=["data:image/png;base64,iVBORw0KGgo..."],
    )
    flags: MessageFlags = Field(
        default_factory=MessageFlags,
        description="Flags que controlam IA, TTS e geracao de imagem",
    )
    instruction: str | None = Field(
        default=None,
        description="Refinamento extra: com --ai define estilo/tom do texto; "
        "com --img define o prompt da imagem a ser gerada",
        examples=["Tom educado e formal, maximo 3 frases"],
    )
    webhook_url: str | None = Field(
        default=None,
        description="URL para callback de status. Se informado, recebe POST "
        "com o resultado ao final do processamento",
        examples=["https://meuapp.com/webhook"],
    )


class MessageCreated(BaseModel):
    """Resposta imediata do POST /messages/send — criacao confirmada."""

    id: int = Field(description="ID interno da mensagem criada")
    status: str = Field(default="pending", description="Status inicial: pending")


class TestEmailRequest(BaseModel):
    """Body para envio de email de teste/diagnostico (mail-tester etc).

    Nao cria Contact e nao persiste Message — apenas dispara o email
    pelo template selecionado e registra um Log para audit.
    """

    to_email: str = Field(
        description="Endereco completo para envio. Aceita endereco unico de mail-tester.com.",
        examples=["test-abcd1234@srv1.mail-tester.com"],
    )
    title: str = Field(
        default="Teste de deliverability — notify",
        description="Subject do email e titulo no template.",
        max_length=255,
    )
    content: str = Field(
        default="Esta e uma mensagem de teste enviada pelo servico notify "
        "para validar deliverability (SPF, DKIM, DMARC).",
        description="Texto do email (sera escapado e inserido em {{content}}).",
    )
    template_slug: str | None = Field(
        default=None,
        description="Slug do template a usar (default: 'default').",
    )


class TestEmailResult(BaseModel):
    """Resultado do POST /messages/test-email."""

    sent: bool
    to_email: str
    template_slug: str
    template_version: int
    smtp_response: dict | None = Field(
        default=None, description="Resposta crua da API de mail merge."
    )
    error: str | None = Field(default=None, description="Mensagem de erro se sent=false.")


class MessageRead(BaseModel):
    """Representacao de uma mensagem persistida."""

    id: int = Field(description="ID interno da mensagem")
    contact_id: int = Field(description="ID do contacto destinatario")
    type: str = Field(description="Tipo: 'text' ou 'media'")
    content_text: str | None = Field(default=None, description="Conteudo textual da mensagem")
    whatsapp_status: str = Field(
        default=STATUS_PENDING,
        description="Status do envio WhatsApp: pending, sent, failed",
    )
    email_status: str = Field(
        default=STATUS_PENDING,
        description="Status do envio Email: pending, sent, failed, skipped",
    )
    email_subject: str | None = Field(
        default=None, description="Titulo do email (gerado por IA ou fallback)"
    )
    tts_audio_url: str | None = Field(
        default=None, description="URL publica do audio TTS gerado, se flags.tts=True"
    )
    created_at: datetime = Field(description="Data de criacao (UTC)")
    updated_at: datetime = Field(description="Data da ultima atualizacao (UTC)")

    model_config = {"from_attributes": True}
