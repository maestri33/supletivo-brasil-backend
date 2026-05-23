# Webhook — Callback de status de mensagem

## O que é

Ao enviar uma mensagem via `POST /api/v1/messages/send`, você pode
informar `webhook_url`. O notify processa a mensagem em background e,
ao final, faz um POST com o resultado na URL:

```
POST {webhook_url}/{message_id}
```

## Como usar

Inclua `webhook_url` no body:

```json
{
  "external_id": "contato-123",
  "title": "Verificação de conta",
  "content": "Seu código é 123456",
  "webhook_url": "http://meu-servico.local/webhook/notify"
}
```

O notify chama: `POST http://meu-servico.local/webhook/notify/142`

## Payload recebido

```json
{
  "event": "message.processed",
  "message_id": 142,
  "contact_id": 7,
  "external_id": "contato-123",
  "type": "text",
  "whatsapp_status": "sent",
  "email_status": "skipped",
  "email_subject": "Verificação de conta",
  "tts_audio_url": null
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `event` | string | Sempre `"message.processed"` |
| `message_id` | int | ID da mensagem no notify |
| `external_id` | string | ID do contacto destinatário |
| `type` | string | `"text"` ou `"media"` |
| `whatsapp_status` | string | `"pending"`, `"sent"`, `"failed"`, `"skipped"` |
| `email_status` | string | `"pending"`, `"sent"`, `"failed"`, `"skipped"` |
| `email_subject` | string | Título usado no email |
| `tts_audio_url` | string\|null | URL do áudio se TTS foi gerado |

## Como implementar no seu serviço

**FastAPI:**
```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhook/notify/{message_id}")
async def notify_callback(message_id: int, request: Request):
    data = await request.json()
    if data["whatsapp_status"] == "sent":
        # atualiza estado no seu banco
        pass
    return {"ok": True}
```

**Express/Node:**
```javascript
app.post('/webhook/notify/:messageId', (req, res) => {
  const { whatsapp_status, email_status, external_id } = req.body;
  // atualiza estado
  res.json({ ok: true });
});
```

## Sem webhook

Se `webhook_url` não for informado, o notify processa normalmente
mas não envia callback. Para consultar o status, use `GET /api/v1/messages/{id}`.
