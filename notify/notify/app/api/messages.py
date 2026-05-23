"""Endpoints de mensagens — envio multicanal (SQLAlchemy 2)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import NotFound
from app.schemas.message import (
    MessageRead,
    MessageSend,
    TestEmailRequest,
    TestEmailResult,
)
from app.services import message_service

router = APIRouter()


@router.post(
    "/send",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar mensagem multicanal",
)
async def send_message(
    payload: MessageSend,
    bg: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> MessageRead:
    """Cria a mensagem (status pending) e enfileira processamento background."""
    message = await message_service.send_message(session, payload)
    bg.add_task(message_service.process_message, payload, message.id)
    return MessageRead.model_validate(message, from_attributes=True)


@router.post(
    "/test-email",
    response_model=TestEmailResult,
    summary="Disparo de email de teste (mail-tester etc) — nao cria Contact",
)
async def test_email(
    payload: TestEmailRequest, session: AsyncSession = Depends(get_session),
) -> TestEmailResult:
    """Helper para validacao de deliverability.

    Uso tipico (mail-tester):
      1. Abra https://www.mail-tester.com/, copie o endereco unico
      2. POST /api/v1/messages/test-email { "to_email": "test-xxx@srv1.mail-tester.com" }
      3. Volte ao site e clique em 'Then check your score'

    Nao persiste Message nem cria Contact — apenas registra Log
    `email.test_sent`/`email.test_failed` para audit.
    """
    return await message_service.send_test_email(session, payload)


@router.get("", response_model=list[MessageRead], summary="Listar mensagens")
async def list_messages(
    contact_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[MessageRead]:
    messages = await message_service.list_messages(
        session, contact_id=contact_id, limit=limit, offset=offset,
    )
    return [MessageRead.model_validate(m, from_attributes=True) for m in messages]


@router.get("/{message_id}", response_model=MessageRead, summary="Obter mensagem")
async def get_message(
    message_id: int, session: AsyncSession = Depends(get_session),
) -> MessageRead:
    msg = await message_service.get_message(session, message_id)
    if msg is None:
        raise NotFound(f"Mensagem {message_id} nao encontrada")
    return MessageRead.model_validate(msg, from_attributes=True)
