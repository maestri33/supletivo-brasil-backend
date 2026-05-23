# WhatsApp — Perfis

## GET /api/v1/whatsapp/profile/{external_id}

Busca o perfil WhatsApp do contacto. Se for conta pessoal,
retorna dados do `fetchProfile`. Se for conta comercial,
faz merge com `fetchBusinessProfile`.

**Resposta (pessoal):**
```json
{
  "external_id": "004d11cb-...",
  "phone": "5543996648750",
  "name": "Victor Maestri",
  "is_business": false,
  "has_picture": true,
  "picture": "https://pps.whatsapp.net/...",
  "status": "...",
  "description": "",
  "website": "",
  "email": "",
  "address": "",
  "category": "",
  "business_hours": "",
  "error": ""
}
```

**Resposta (comercial):**
```json
{
  "external_id": "637dab8c-...",
  "phone": "554220181533",
  "name": "",
  "is_business": true,
  "has_picture": true,
  "picture": "https://pps.whatsapp.net/...",
  "status": "...",
  "description": "",
  "website": "https://estacio.br/",
  "email": "",
  "address": "R. Padre Camargo, 844 - Centro, Palmeira - PR",
  "category": "Education",
  "business_hours": "America/Sao_Paulo",
  "error": ""
}
```

Todos os 14 campos sempre presentes, mesmo que vazios.

## GET /api/v1/whatsapp/profiles/

Mesma lógica acima aplicada a TODOS os contactos com telefone.
Retorna lista paginada com `count` e `items[]`.
