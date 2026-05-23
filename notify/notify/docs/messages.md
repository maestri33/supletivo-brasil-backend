# POST /api/v1/messages/send

## Request

```json
{
  "external_id": "contato-123",     // obrigatorio — ID do contacto
  "title": "Verificacao",           // opcional — extrai do # Titulo do content se nao vier
  "content": "texto ou URL .md",    // obrigatorio — corpo da mensagem
  "flags": {
    "ai": false,                     // reescreve texto via AI
    "tts": false,                    // gera audio e envia voice note
    "img": false                     // gera imagem e envia como midia
  },
  "instruction": "estilo extra",     // opcional — refinamento para --ai ou --img
  "media_url": "https://...",       // opcional — midia anexa
  "webhook_url": "http://..."       // opcional — callback de status
}
```

## Response (201 Created)

Retorna o objeto completo com status `pending`. O processamento
(AI, WhatsApp, Email, TTS) roda em background.

```json
{
  "id": 142,
  "contact_id": 7,
  "type": "text",
  "content_text": "...",
  "whatsapp_status": "pending",
  "email_status": "pending",
  "email_subject": "Verificacao",
  "tts_audio_url": null,
  "created_at": "...",
  "updated_at": "..."
}
```

## Content .md (Markdown via URL)

Se `content` for uma URL terminada em `.md` (ex: `https://meusite.com/noticias.md`),
o notify faz o download do arquivo e extrai o texto antes de processar.

### Resolução do título

A ordem de prioridade para definir o título da mensagem é:

| Prioridade | Fonte | Exemplo |
|---|---|---|
| 1 | Campo `title` no payload | `"title": "Urgente"` |
| 2 | Primeiro `# Titulo` dentro do .md | `# Noticia do dia` |
| 3 | Fallback | `Nova mensagem` |

### Exemplo 1 — title no payload (vence)

```json
{
  "external_id": "contato-123",
  "title": "Comunicado Importante",
  "content": "https://meusite.com/noticias.md"
}
```

← WhatsApp: `*Comunicado Importante*\n\n...`
← Email assunto: `Comunicado Importante`

### Exemplo 2 — sem title, extrai do .md

Conteúdo do arquivo `noticias.md`:
```markdown
# Resultado das Eleicoes

Candidato A venceu com 52% dos votos...
```

```json
{
  "external_id": "contato-123",
  "content": "https://meusite.com/noticias.md"
}
```

← Título extraído: `Resultado das Eleicoes`
← WhatsApp: `*Resultado das Eleicoes*\n\nCandidato A venceu...`

### Exemplo 3 — sem title, sem # no .md

```json
{
  "external_id": "contato-123",
  "content": "https://meusite.com/simples.md"
}
```

← Título fallback: `Nova mensagem`

### Com --ai

Se `flags.ai: true`, o notify primeiro extrai o texto do .md,
depois chama o AI service `/text` para reescrever.
A extração de título acontece ANTES da reescrita (usa o .md original).

## Flags

| Flag | Efeito |
|---|---|
| `ai` | Chama AI service /text para reescrever o content |
| `img` | Chama AI service /image para gerar imagem. Converte type=media. Desativa TTS |
| `tts` | Chama AI service /tts para gerar audio. Envia voice note no WhatsApp |

`img` e `tts` são mutuamente exclusivos — img vence.

## Webhook

Ver [webhook.md](https://notify.v7m.net/media/instructions/webhook.md) para o contrato completo.
