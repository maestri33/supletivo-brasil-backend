# Integrações — profiles

## CPFHub.io (externo) — `app/integrations/cpfhub.py`
- **Para quê:** lookup de identidade por CPF (nome, gênero, data de nascimento)
  para enriquecer o perfil **após** a criação.
- **Endpoint:** `GET {CPFHUB_BASE_URL}/cpf/{cpf}` com header `x-api-key`.
- **Config (.env):** `CPFHUB_API_KEY` (vazio = desabilitado), `CPFHUB_BASE_URL`
  (default `https://api.cpfhub.io`), `CPFHUB_TIMEOUT_SECONDS` (default 5.0).
- **Resiliência:** retry em status transientes (429/5xx), 3 tentativas, backoff.
  Retorna `CPFHubIdentity` ou `None`. **Best-effort:** qualquer falha é engolida
  com `logger.warning` (só `type(exc)`), e o perfil recém-criado segue válido
  sem enriquecimento. Nunca quebra o fluxo de criação.

## Internas (outros microsserviços)
- Nenhuma chamada httpx interna hoje. Relação com `auth` é só por **FK
  cross-schema** (shadow table read-only `auth.users` em `app/db.py`), não por HTTP.
- Se precisar falar com outro serviço, criar client em `integrations/<servico>.py`
  (httpx async) — nunca importar código alheio.
