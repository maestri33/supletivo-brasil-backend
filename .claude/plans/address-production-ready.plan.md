# Plan: Address — Identidade UUID

**Source PRD**: .claude/prds/address-production-ready.prd.md
**Selected Milestone**: #1 — Identidade UUID (PK integer → UUID nas 3 tabelas)
**Complexity**: Medium

## Summary
Trocar a PK das 3 tabelas do schema `addresses` (`addresses`, `entity_address_details`, `entity_addresses`) de `integer autoincrement` para `UUID`, alinhando à CONVENTION §4. As referências cross-service usam `external_id` (já UUID), então o raio de impacto externo é baixo — a mudança é interna ao serviço (PK + FK interna `entity_addresses.address_id → entity_address_details.id` + tipos em schemas/api/services + nova migração Alembic).

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| UUID column | `address/app/models/address.py:22` | `mapped_column(PG_UUID(as_uuid=True), ...)` — reusar para as novas PKs |
| Naming/constraints | `address/app/db.py:18` | `NAMING_CONVENTION` já define `pk`/`fk` — a migração deve respeitar |
| Erros de domínio | `address/app/services/address_service.py:51` | `raise NotFound(f'Address "{address_id}" não encontrado')` |
| Migração | `address/alembic/versions/2026-05-22_0001_initial_addresses_schema.py` | estilo/revisão a espelhar na nova revisão |
| Tests | — | **Não há `address/tests/`** hoje; cobertura completa é o Milestone #2, não este |

## Files to Change
| File | Action | Why |
|---|---|---|
| `address/app/models/address.py` | UPDATE | `Address.id` int→UUID (`default=uuid.uuid4`) |
| `address/app/models/entity_address.py` | UPDATE | `EntityAddressDetail.id`, `EntityAddress.id` int→UUID; FK `address_id` int→UUID |
| `address/app/schemas/address.py` | UPDATE | `AddressRead.id: int` → `UUID` (linha ~196) |
| `address/app/schemas/entity_address.py` | UPDATE | `id: int` → `UUID` (linhas 12 e 29) |
| `address/app/api/addresses.py` | UPDATE | path params `address_id: int` → `UUID` (get/patch/delete, linhas 70/76/82) |
| `address/app/services/address_service.py` | UPDATE | assinaturas `address_id: int` → `UUID` (48/100/120); `session.get` segue OK |
| `address/app/services/entity_address_service.py` | UPDATE | `_by_id(ea_id: int)` → `UUID` (34); `ea.id` em filename de proof segue OK (89) |
| `address/alembic/versions/2026-05-22_0002_pk_uuid.py` | CREATE | migração trocando PKs/FK para UUID |

## Tasks
### Task 1: Models → UUID
- **Action**: nas 3 classes, trocar `id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)` por `id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`. Em `EntityAddress.address_id`, trocar `int`→`UUID` mantendo a FK `entity_address_details.id (ondelete=SET NULL)`. Remover import `Integer` se ficar órfão; adicionar `import uuid` / `from uuid import UUID`.
- **Mirror**: `address/app/models/address.py:22` (PG_UUID).
- **Validate**: `cd address && ruff check app/models`.

### Task 2: Schemas → UUID
- **Action**: `AddressRead.id` e os dois `id` de `entity_address.py` viram `UUID`. Confirmar `from uuid import UUID` nos schemas.
- **Mirror**: tipos Pydantic v2 já em uso.
- **Validate**: `ruff check app/schemas`.

### Task 3: API + Services → UUID
- **Action**: path params e assinaturas de serviço `address_id`/`ea_id` de `int`→`UUID`. FastAPI valida UUID no path automaticamente (404/422 para inválido). `session.get(Address, uuid)` e `where(EntityAddress.id == uuid)` funcionam sem mudança de lógica.
- **Mirror**: `address_service.py:49` (`session.get`).
- **Validate**: `ruff check app/api app/services`.

### Task 4: Migração Alembic
- **Action**: criar revisão `0002` (down_revision = 0001) que converte as PKs e a FK interna para UUID. **Estratégia depende da Open Question (greenfield vs dados):**
  - *Greenfield (assumido)*: drop/recreate das 3 tabelas com PK UUID — mais simples (§14).
  - *Com dados*: `ALTER`/backfill com `gen_random_uuid()` + recriação da FK `entity_addresses.address_id` — preserva linhas.
- **Mirror**: `2026-05-22_0001_initial_addresses_schema.py`.
- **Validate**: `uv run alembic upgrade head` em banco limpo; depois `alembic downgrade -1 && alembic upgrade head`.

## Validation
```bash
cd address
ruff check . && ruff format --check .
uv run alembic upgrade head            # migração aplica em banco limpo
# round-trip mínimo (smoke, cobertura completa fica no Milestone #2):
#   POST /api/v1/addresses → resposta com id UUID → GET /{id} 200 → DELETE 204
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Migração PK→UUID quebra FK interna | Média | Recriar FK `entity_addresses.address_id` na mesma revisão; testar downgrade/upgrade |
| Path param antigo (int) em consumidores | Baixa | Consumidores usam `external_id` (UUID) e rotas `by-external-id`, não o `{address_id}` interno; confirmar no Milestone #3 |
| `default=uuid.uuid4` client-side vs `gen_random_uuid()` server-side | Baixa | Client-side evita dependência de extensão pgcrypto (§14); decidido client-side |

## Acceptance
- [ ] 3 tabelas com PK UUID; FK interna UUID
- [ ] schemas/api/services tipados como UUID; `ruff` limpo
- [ ] migração `0002` aplica em banco limpo e faz downgrade/upgrade
- [ ] smoke round-trip (create→get→delete) retorna id UUID
- [ ] Patterns espelhados (PG_UUID de address.py), não reinventados

---
*Próximo: confirmar greenfield-vs-dados (Open Question) e então implementar via `tdd-workflow`.*
