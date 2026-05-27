# Integrações — candidate

Todas via `httpx.AsyncClient(base_url=...)` + `request_with_retry`. URLs no `.env`.

| Client | Serviço | Endpoints usados | Notas |
|--------|---------|------------------|-------|
| `AuthClient` | auth (`AUTH_BASE_URL`) | `POST /api/v1/check`, `/register` (role=lead), `/login` | register devolve `external_id` |
| `JwtClient` | jwt (`JWT_BASE_URL`) | `POST /api/v1/tokens/refresh` | refresh de tokens |
| `NotifyClient` | notify (`NOTIFY_BASE_URL`) | `GET /contacts/{id}`, `PATCH /contacts/{id}/email`, `POST /messages/send` | usado em captured e notificações |
| `ProfilesClient` | profiles (`PROFILES_BASE_URL`) | `GET /profiles/{id}`, `GET /profiles/first-name/{id}`, `PATCH /profiles/{id}` | CPF do titular do PIX vem daqui (campo `cpf`) |
| `AddressClient` | address (`ADDRESSES_BASE_URL`) | check CEP, create address, bind entity por CEP | `entity_type="lead"` |
| `AsaasClient` | asaas (`ASAAS_BASE_URL`) | `POST /api/v1/pixkey`, `GET /api/v1/pixkey/{id}` | valida DICT + titular; **único** caminho p/ Asaas (§12) |
| `DocumentsClient` | documents (`DOCUMENTS_BASE_URL`) | `GET/PUT /api/v1/documentos/{id}`, `POST .../imagens/{slot}` | slots RG/CNH + `foto` (selfie) |
| `AIClient` | ai (`AI_BASE_URL`) | `POST /api/v1/image/vision` | descreve selfie; o ai baixa a URL server-side |
| `RolesClient` | roles (`ROLES_BASE_URL`) | `GET /api/v1/role/{id}`, `POST /api/v1/role/{id}/up/{role}` | conclusão promove p/ `training` |

## Selfie (fluxo)
1. upload da selfie → documents slot `foto`;
2. `image_url = {DOCUMENTS_BASE_URL}/api/v1/documentos/{id}/imagens/foto`;
3. `ai.vision(image_url)` (o ai faz GET da URL e manda bytes ao Gemini);
4. heurística de "pessoa real"; falha do ai não bloqueia.

## Suposições a confirmar (contratos)
- profiles expõe o CPF em `cpf` (fallback testado: `document`/`cpf_cnpj`).
- address usa `entity_type="lead"` para vincular o endereço do candidato.
- Se algum contrato divergir, ajustar o client/serviço correspondente.

## Pendente
- `training` (`TrainingClient`): a criar quando o serviço existir; hoje a
  conclusão só promove o papel via `roles`.
