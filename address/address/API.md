# Address Service — API

Base: `/api/v1`. Erros de domínio retornam `{ "code": "...", "message": "..." }`.

## Endereços de usuário (`auth.users`)

### `POST /api/v1/addresses`
Cria um endereço de um usuário (`external_id` deve existir em `auth.users`).

```json
{
  "external_id": "11111111-1111-1111-1111-111111111111",
  "kind": "home",
  "zipcode": "80010-000",
  "street": "Rua Teste",
  "number": "100",
  "city": "Curitiba",
  "state": "PR",
  "country": "BR",
  "lat": "-25.4284",
  "lng": "-49.2733"
}
```

**201**
```json
{
  "id": 1,
  "external_id": "11111111-1111-1111-1111-111111111111",
  "kind": "home",
  "zipcode": "80010000",
  "street": "Rua Teste",
  "number": "100",
  "complement": null,
  "neighborhood": null,
  "city": "Curitiba",
  "state": "PR",
  "country": "BR",
  "lat": "-25.4284",
  "lng": "-49.2733",
  "created_at": "...",
  "updated_at": "..."
}
```

`kind` aceita aliases pt-br (`casa`→home, `cobranca`→billing, `entrega`→shipping).
`zipcode` é normalizado p/ 8 dígitos. `external_id` inexistente em `auth.users` → **422**.

### `GET /api/v1/addresses?external_id=&kind=&limit=&offset=`
Lista com filtros opcionais e paginação (`limit` 1–100, default 20).

### `GET /api/v1/addresses/{id}` — detalhe (404 se não achar)
### `PATCH /api/v1/addresses/{id}` — atualização parcial (envia só o que muda)
### `DELETE /api/v1/addresses/{id}` — hard delete (**204**)
### `GET /api/v1/addresses/by-external-id/{eid}` — todos os endereços do usuário
### `GET /api/v1/addresses/by-external-id/{eid}/{kind}/current` — mais recente do kind

### `GET /api/v1/addresses/cep/{zipcode}`
Lookup **real** na ViaCEP.

**200**
```json
{
  "zipcode": "01310100",
  "street": "Avenida Paulista",
  "complement": "de 612 a 1510 - lado par",
  "neighborhood": "Bela Vista",
  "city": "São Paulo",
  "state": "SP"
}
```
CEP inválido (formato) → **422**; CEP inexistente → **404**.

---

## Entidades (vínculo polimórfico)

`entity_type` identifica o tipo (`user`, `hub`, `atendimento`, `parceiro`…) e
`external_id` é o ID externo (string). A combinação é única.

### `GET /api/v1/entities/{entity_type}/{external_id}`
**Get or create.** Cria com endereço vazio se não existir.

**200**
```json
{
  "id": 1,
  "entity_type": "user",
  "external_id": "victor",
  "proof_file": null,
  "address": {
    "id": 1, "street": null, "number": null, "complement": null,
    "neighborhood": null, "city": null, "state": null, "zipcode": null,
    "lat": null, "lng": null, "created_at": "...", "updated_at": "..."
  },
  "created_at": "...",
  "updated_at": "..."
}
```

### `POST /api/v1/entities/{entity_type}/{external_id}/cep?cep={cep}`
Consulta ViaCEP e **preenche** o endereço (street, complement, neighborhood, city,
state, zipcode). `lat`/`lng` não são sobrescritos. Se a ViaCEP não achar o CEP, só
o `zipcode` é salvo. **404** se a entidade não existir.

### `POST /api/v1/entities/{entity_type}/{external_id}/proof`
Upload de comprovante (multipart `file`). Salvo em `UPLOAD_DIR`, atualiza `proof_file`.
**404** se a entidade não existir.

```bash
curl -X POST "http://localhost:8000/api/v1/entities/user/victor/proof" -F "file=@comprovante.pdf"
```

### `POST /api/v1/entities/{entity_type}/{external_id}/unlink`
Desvincula o endereço atual (registro antigo é renomeado, histórico preservado) e
cria um novo vazio.

---

## Operacional
`GET /health` · `GET /ready` (SELECT 1 real) · `GET /status` (versão + uptime).

## Comportamento esperado (ViaCEP / webhook)

| Situação | Resposta |
|----------|----------|
| CEP válido na ViaCEP | endereço preenchido (logradouro, bairro, cidade, UF, complemento) |
| CEP inexistente | só o `zipcode` é salvo; demais campos mantêm o valor anterior |
| ViaCEP fora do ar | loga warning, salva só o `zipcode` |
| `lat`/`lng` | nunca alterados pelo ViaCEP — só via PATCH |
| Webhook | toda criação/alteração/deleção de Address dispara POST p/ `WEBHOOK_URL` |
