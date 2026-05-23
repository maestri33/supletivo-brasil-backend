# Evolution API — Chat Endpoints

**Base URL:** `http://10.10.10.149`  
**API Key:** `7A3F8C2B1D4E5F6789ABCDEF01234567`  
**Content-Type:** `application/json`

---

## POST /chat/whatsappNumbers/{instance}

Verifica se um ou mais números existem no WhatsApp e retorna nome + JID real.

### Requisição

```bash
curl -X POST http://10.10.10.149/chat/whatsappNumbers/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{"numbers": ["5543996648750", "554220181533"]}'
```

### Resposta

```json
[
  {
    "jid": "554396648750@s.whatsapp.net",
    "exists": true,
    "number": "5543996648750",
    "name": "Victor Maestri",
    "lid": "lid"
  },
  {
    "jid": "554220181533@s.whatsapp.net",
    "exists": true,
    "number": "554220181533"
  }
]
```

### Campos da resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jid` | string | JID real no WhatsApp — **use este**, não o número que você montou |
| `exists` | boolean | `true` se a conta existe no WhatsApp |
| `number` | string | Número consultado (espelho do input) |
| `name` | string? | Nome público da pessoa — pode vir ausente se a privacidade bloquear |
| `lid` | string? | `"lid"` para contas verificadas com linked ID; ausente para contas sem |

### Comportamento

- **Array de entrada**: aceita múltiplos números em uma única chamada
- **JID corrigido**: o WhatsApp normaliza o JID — `5543996648750` virou `554396648750@s.whatsapp.net`. Sempre use o `jid` retornado nas chamadas subsequentes
- **Nome opcional**: `name` só aparece se a pessoa não bloqueou nas configurações de privacidade
- **Conta inexistente**: se o número não tem WhatsApp, `exists` vem `false` e `jid` vem vazio

---

## POST /chat/fetchProfile/{instance}

Retorna perfil completo: nome, foto, status/recado.

### Requisição

```bash
curl -X POST http://10.10.10.149/chat/fetchProfile/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{"number": "554396648750"}'
```

### Resposta

```json
{
  "status": "Hey there! I am using WhatsApp",
  "profilePictureUrl": "https://pps.whatsapp.net/v/t61.24694-24/671097495_971786672011737_2040477066766484798_n.jpg?ccb=11-4&oh=...",
  "name": "Victor Maestri",
  "isBusiness": false
}
```

### Campos da resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | Recado/status da pessoa |
| `profilePictureUrl` | string? | URL da foto de perfil (temporária, expira) |
| `name` | string | Nome público no WhatsApp |
| `isBusiness` | boolean | Se é conta WhatsApp Business |

> **IMPORTANTE:** Use o JID retornado pelo `/chat/whatsappNumbers`, não o número original. A URL da foto é temporária e **expira** — faça download se precisar armazenar.

---

## POST /chat/fetchProfilePictureUrl/{instance}

Retorna apenas a URL da foto de perfil.

### Requisição

```bash
curl -X POST http://10.10.10.149/chat/fetchProfilePictureUrl/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{"number": "554396648750"}'
```

### Resposta

```json
{
  "profilePictureUrl": "https://pps.whatsapp.net/v/t61.24694-24/671097495_971786672011737_2040477066766484798_n.jpg?ccb=11-4&oh=..."
}
```

---

## GET /chat/findChatByRemoteJid/{instance}

Busca um chat específico pelo JID no banco de dados local.

### Requisição

```bash
curl "http://10.10.10.149/chat/findChatByRemoteJid/default?remoteJid=554396648750@s.whatsapp.net" \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567"
```

### Resposta (chat com histórico)

```json
{
  "id": "cmosr9z4x004fgg7nnco6jtn6",
  "remoteJid": "554396648750@s.whatsapp.net",
  "pushName": null,
  "profilePicUrl": "https://pps.whatsapp.net/...",
  "updatedAt": "2026-05-05T15:31:17.000Z",
  "lastMessage": {
    "messageType": "documentMessage",
    "message": {
      "documentMessage": {
        "caption": "..."
      }
    }
  },
  "unreadCount": null,
  "isSaved": true
}
```

### Resposta (sem chat)

```json
null
```

> **IMPORTANTE:** Este endpoint consulta o **banco de dados local**, não o WhatsApp. Só retorna dados se houver histórico salvo (config: `DATABASE_SAVE_DATA_CHATS=true`). Usa o **JID com sufixo** (`@s.whatsapp.net`).

---

## POST /chat/findChats/{instance}

Busca lista de chats no banco de dados local com filtros.

### Requisição — todos os chats

```bash
curl -X POST http://10.10.10.149/chat/findChats/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Requisição — filtrar por JID

```bash
curl -X POST http://10.10.10.149/chat/findChats/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{"where": {"remoteJid": "554396648750@s.whatsapp.net"}}'
```

### Resposta

```json
[
  {
    "id": "cmosr9z4x004fgg7nnco6jtn6",
    "remoteJid": "554396648750@s.whatsapp.net",
    "pushName": "Victor Maestri",
    "profilePicUrl": "https://pps.whatsapp.net/...",
    "updatedAt": "2026-05-05T15:31:17.000Z",
    "windowActive": false,
    "lastMessage": { ... },
    "unreadCount": null,
    "isSaved": true
  }
]
```

> **IMPORTANTE:** Também consulta o **banco de dados local**. Chats que nunca trocaram mensagem nesta instância **não aparecem**. Para apenas verificar existência de um número, use `/chat/whatsappNumbers`.

---

## Fluxo recomendado

```
1. POST /chat/whatsappNumbers     → verifica existência + obtém JID real + nome
2. POST /chat/fetchProfile         → obtém foto, status/recado, isBusiness
3. POST /chat/fetchProfilePictureUrl → (opcional) obter apenas a URL da foto

(Esses abaixo só funcionam se há histórico de mensagens salvo)

4. GET  /chat/findChatByRemoteJid  → buscar chat específico no banco
5. POST /chat/findChats            → listar chats com filtros
```

## Observações gerais

- **SEMPRE use o `jid` retornado** pelo `whatsappNumbers` — nunca monte o JID manualmente (`55439...@s.whatsapp.net`). O WhatsApp pode normalizar os dígitos
- **URLs de foto expiram**: as URLs de `profilePictureUrl` têm TTL curto (horas/dias). Faça download se precisar persistir
- **`findChats` vs `whatsappNumbers`**: o primeiro consulta banco local (precisa de histórico), o segundo consulta o WhatsApp diretamente
- **`findChatByRemoteJid` usa query string** (`?remoteJid=...`), enquanto `findChats` usa **body JSON** com `where`
