# Evolution API — Guia de Endpoints sendMessage

**Instância:** `default`  
**Base URL:** `http://10.10.10.149`  
**API Key:** `7A3F8C2B1D4E5F6789ABCDEF01234567`  
**Content-Type:** `application/json`

---

## 1. sendText

**Endpoint:** `POST /message/sendText/default`

Envia uma mensagem de texto simples.

```json
{
  "number": "554396648750",
  "text": "Olá, mundo!"
}
```

**Resposta (201):** Retorna `key.id`, `status: "PENDING"`, `messageType: "conversation"`.

> ⚠️ O número pode ser enviado com ou sem `@s.whatsapp.net`. A API normaliza automaticamente.

---

## 2. sendMedia

**Endpoint:** `POST /message/sendMedia/default`

Envia imagem, vídeo, áudio ou documento. O campo `mediatype` define o tipo.

### Tipos suportados

| mediatype | Descrição | Campos extras |
|-----------|-----------|---------------|
| `image` | Imagem (converte para JPEG) | `caption`, `mimetype` |
| `video` | Vídeo com thumbnail | `caption` |
| `audio` | Arquivo de áudio | — |
| `document` | Qualquer arquivo | `fileName`, `caption` |

### Exemplo — Imagem via URL

```json
{
  "number": "554396648750",
  "mediatype": "image",
  "media": "https://picsum.photos/200/300",
  "caption": "Legenda da imagem"
}
```

### Exemplo — Imagem via base64

```json
{
  "number": "554396648750",
  "mediatype": "image",
  "media": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
  "caption": "Legenda da imagem"
}
```

> ⚠️ **IMPORTANTE:** O base64 deve ser PURO, sem o prefixo `data:image/png;base64,`. Com prefixo retorna erro `"Owned media must be a url or base64"`.

### Exemplo — Documento PDF

```json
{
  "number": "554396648750",
  "mediatype": "document",
  "media": "https://example.com/documento.pdf",
  "fileName": "documento.pdf",
  "caption": "Segue o documento"
}
```

> ⚠️ Para `document`, defina sempre `fileName`, caso contrário o WhatsApp mostrará nome genérico.

### Exemplo — Vídeo

```json
{
  "number": "554396648750",
  "mediatype": "video",
  "media": "https://www.w3schools.com/html/mov_bbb.mp4",
  "caption": "Assista o vídeo"
}
```

### Exemplo — Áudio

```json
{
  "number": "554396648750",
  "mediatype": "audio",
  "media": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
}
```

---

## 3. sendSticker

**Endpoint:** `POST /message/sendSticker/default`

Envia um sticker (figurinha). Aceita URL ou base64 puro.

### Exemplo — URL (.webp recomendado)

```json
{
  "number": "554396648750",
  "sticker": "https://www.gstatic.com/webp/gallery/1.webp"
}
```

### Exemplo — base64 puro

```json
{
  "number": "554396648750",
  "sticker": "UklGRiQAAABXRUJQVlA4..."
}
```

> ⚠️ **IMPORTANTE:** Não use prefixo `data:image/png;base64,` — apenas base64 puro. Formatos recomendados: WebP ou PNG pequeno. O WhatsApp tem limite de ~500KB para stickers.

---

## 4. sendLocation

**Endpoint:** `POST /message/sendLocation/default`

Envia uma localização no mapa.

```json
{
  "number": "554396648750",
  "latitude": -23.5505,
  "longitude": -46.6333,
  "name": "São Paulo",
  "address": "Av. Paulista, 1000"
}
```

> `name` e `address` são opcionais mas recomendados para contexto.

---

## 5. sendContact

**Endpoint:** `POST /message/sendContact/default`

Envia um ou mais contatos (vCard).

```json
{
  "number": "554396648750",
  "contact": [
    {
      "fullName": "João Silva",
      "phoneNumber": "+5511999999999",
      "organization": "Empresa XYZ",
      "email": "joao@email.com"
    }
  ]
}
```

> ⚠️ Use `fullName` e `phoneNumber` (não `displayName` nem `vcard`). A API gera o vCard automaticamente. Para múltiplos contatos, adicione mais objetos no array.

---

## 6. sendPoll

**Endpoint:** `POST /message/sendPoll/default`

Envia uma enquete interativa.

```json
{
  "number": "554396648750",
  "name": "Qual sua cor favorita?",
  "selectableCount": 1,
  "values": ["Azul", "Vermelho", "Verde", "Amarelo"]
}
```

> `selectableCount` = quantas opções o usuário pode escolher. Máximo de opções: 12.

---

## 7. sendButtons

**Endpoint:** `POST /message/sendButtons/default`

Envia mensagem com botões interativos. Suporta 3 tipos de botão.

### Botões de resposta rápida (reply)

```json
{
  "number": "554396648750",
  "title": "Confirmação",
  "description": "Deseja continuar?",
  "footer": "Escolha uma opção",
  "buttons": [
    {"type": "reply", "displayText": "Sim"},
    {"type": "reply", "displayText": "Não"}
  ]
}
```

### Botão de URL

```json
{
  "number": "554396648750",
  "title": "Links Úteis",
  "description": "Acesse nossos sites",
  "footer": "Clique abaixo",
  "buttons": [
    {"type": "url", "displayText": "Google", "url": "https://google.com"}
  ]
}
```

### Botão de cópia

```json
{
  "number": "554396648750",
  "title": "Código de Pix",
  "description": "Copie o código abaixo",
  "footer": "Chave Pix",
  "buttons": [
    {"type": "copy", "displayText": "Copiar Chave", "copyText": "123e4567-e89b-12d3-a456-426614174000"}
  ]
}
```

### Com thumbnail

```json
{
  "number": "554396648750",
  "title": "Confirmação com Imagem",
  "description": "Deseja continuar?",
  "footer": "Rodapé",
  "thumbnailUrl": "https://picsum.photos/100/100",
  "buttons": [
    {"type": "reply", "displayText": "Sim"},
    {"type": "reply", "displayText": "Não"}
  ]
}
```

> ⚠️ Máximo de 3 botões por mensagem. O título aparece em negrito com asteriscos automáticos.

---

## 8. sendReaction

**Endpoint:** `POST /message/sendReaction/default`

Reage a uma mensagem específica com emoji.

```json
{
  "number": "554396648750",
  "key": {
    "remoteJid": "554396648750@s.whatsapp.net",
    "id": "3EB07F0A7C7F0830FABB3C",
    "fromMe": true
  },
  "reaction": "❤️"
}
```

> ⚠️ O `key.id` é o ID da mensagem original (retornado no campo `key.id` da resposta do envio). Para remover reação, envie `reaction: ""`.

---

## 9. sendWhatsAppAudio

**Endpoint:** `POST /message/sendWhatsAppAudio/default`

Envia áudio que aparece como mensagem de voz do WhatsApp (PTT — Push to Talk).

```json
{
  "number": "554396648750",
  "audio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
}
```

> ⚠️ Diferente do `sendMedia` com `mediatype: "audio"`, este endpoint força o formato de mensagem de voz nativa do WhatsApp (com waveform e UI de áudio do WhatsApp). Ideal para notas de voz.

---

## 10. sendStatus

**Endpoint:** `POST /message/sendStatus/default`

Publica um status (stories) no WhatsApp.

### Status de texto

```json
{
  "number": "554396648750",
  "type": "text",
  "content": "Meu primeiro status via API!",
  "backgroundColor": "#000000",
  "font": 1,
  "statusJidList": ["554396648750@s.whatsapp.net"]
}
```

### Status de imagem

```json
{
  "number": "554396648750",
  "type": "image",
  "content": "https://picsum.photos/200/300",
  "caption": "Status com imagem",
  "statusJidList": ["554396648750@s.whatsapp.net"]
}
```

**Fontes disponíveis (número):**

| Valor | Fonte |
|-------|-------|
| 1 | SERIF |
| 2 | NORICAN_REGULAR |
| 3 | BRYNDAN_WRITE |
| 4 | BEBASNEUE_REGULAR |
| 5 | OSWALD_HEAVY |

> ⚠️ **BUG CONHECIDO:** `font: 0` (SANS_SERIF) não funciona! O código em `whatsapp.baileys.service.ts:2694` usa `if (!status.font)` que rejeita o valor `0` por ser falsy em JavaScript. Use font 1-5.
>
> ⚠️ `statusJidList` deve ter pelo menos 1 JID. Use `allContacts: true` para enviar a todos os contatos.

---

## ❌ Endpoints NÃO Suportados (Baileys)

### sendList — Bug interno

`POST /message/sendList/default` retorna `TypeError: this.isZero is not a function`. É um bug na biblioteca libsignal usada pelo Baileys. Listas interativas **não funcionam** com Baileys + Node.js v20.10.0.

### sendTemplate — Meta Business API apenas

`POST /message/sendTemplate/default` retorna `Method not available in the Baileys service`. Templates são exclusivos da WhatsApp Cloud API (Meta Business), não do Baileys (WhatsApp Web).

### sendPtv — Incompatibilidade Node.js

`POST /message/sendPtv/default` retorna erro de WebAssembly `invalid value type 'stringref'`. O modulo de processamento de vídeo requer Node.js 22+ com flag `--experimental-wasm-stringref`.

---

## Resumo rápido

| Endpoint | Status | Notas |
|----------|--------|-------|
| sendText | ✅ | Texto simples |
| sendMedia (image) | ✅ | URL ou base64 PURO |
| sendMedia (video) | ✅ | URL recomendado |
| sendMedia (audio) | ✅ | URL recomendado |
| sendMedia (document) | ✅ | Sempre defina fileName |
| sendSticker | ✅ | WebP URL ou base64 PURO |
| sendLocation | ✅ | lat/long obrigatórios |
| sendContact | ✅ | Use fullName + phoneNumber |
| sendPoll | ✅ | Até 12 opções |
| sendButtons | ✅ | Máx. 3 botões (reply/url/copy) |
| sendReaction | ✅ | Precisa key.id da msg original |
| sendWhatsAppAudio | ✅ | Formato voz nativa |
| sendStatus | ✅ | font: 1-5 (0 bugado) |
| sendList | ❌ | Bug libsignal |
| sendTemplate | ❌ | Só Meta Business API |
| sendPtv | ❌ | Precisa Node 22+ |
