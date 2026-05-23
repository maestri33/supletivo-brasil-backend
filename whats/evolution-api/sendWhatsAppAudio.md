# POST /message/sendWhatsAppAudio/{instance}

Envia um áudio com aparência de **gravado na hora** (mensagem de voz nativa do WhatsApp), com waveform e player de PTT (Push to Talk).

## Diferença crucial

| | `sendMedia` (audio) | `sendWhatsAppAudio` |
|---|---|---|
| **Aparência** | Arquivo anexado | Como se tivesse **gravado** |
| **Player** | Player genérico de mídia | Bolinha verde com waveform |
| **PTT** | ❌ `ptt: false` | ✅ `ptt: true` |
| **Codec** | Mantém original | Converte para Opus |
| **Waveform** | ❌ Não | ✅ Gerada automaticamente |

## Requisição

```bash
curl -X POST http://10.10.10.149/message/sendWhatsAppAudio/default \
  -H "apikey: 7A3F8C2B1D4E5F6789ABCDEF01234567" \
  -H "Content-Type: application/json" \
  -d '{
    "number": "554396648750",
    "audio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
  }'
```

### Body

```json
{
  "number": "554396648750",
  "audio": "<URL ou base64 do arquivo de áudio>"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `number` | string | Sim | Número do destinatário |
| `audio` | string | Sim | URL pública ou base64 puro do áudio |
| `delay` | number | Não | Atraso em ms antes do envio |
| `quoted` | object | Não | Mensagem a ser respondida |
| `mentioned` | string[] | Não | JIDs a mencionar |

## Resposta (201)

```json
{
  "key": {
    "remoteJid": "554396648750@s.whatsapp.net",
    "fromMe": true,
    "id": "3EB040C66A518ACAA9076D"
  },
  "pushName": "Você",
  "status": "PENDING",
  "message": {
    "audioMessage": {
      "url": "https://mmg.whatsapp.net/v/t62.7114-24/...",
      "mimetype": "audio/ogg; codecs=opus",
      "seconds": 372,
      "ptt": true,
      "waveform": {
        "0": 21, "1": 23, "2": 38, ...
      }
    }
  },
  "messageType": "audioMessage",
  "messageTimestamp": 1777995123,
  "source": "web"
}
```

### Campos da resposta

| Campo | Descrição |
|-------|-----------|
| `key.id` | ID único da mensagem (use para reações, citações) |
| `status` | `"PENDING"` → `"SERVER_ACK"` → `"DELIVERY_ACK"` → `"READ"` |
| `audioMessage.ptt` | **`true`** = aparece como gravação de voz |
| `audioMessage.seconds` | Duração em segundos |
| `audioMessage.waveform` | Array de amplitudes da onda sonora (64 bytes) |
| `audioMessage.mimetype` | `"audio/ogg; codecs=opus"` — codec nativo do WhatsApp |

## Exemplo com base64

```json
{
  "number": "554396648750",
  "audio": "T2dnUwACAAAAAAA..."
}
```

> ⚠️ Mesma regra do sendMedia/sendSticker: **base64 puro**, sem prefixo `data:audio/mpeg;base64,`.

## Observações

- O WhatsApp **converte automaticamente** o áudio para Opus (codec nativo)
- Formatos de entrada aceitos: MP3, WAV, OGG, M4A, AAC — qualquer formato suportado pelo ffmpeg/libav
- O `waveform` é gerado automaticamente pelo Baileys — não precisa enviar
- Ideal para chatbots de voz, notas de voz automatizadas, ou simular gravações
- Para enviar como **arquivo de áudio** (ex: música, podcast), use `sendMedia` com `mediatype: "audio"` — nesse caso o WhatsApp mostra nome do arquivo e não gera waveform
