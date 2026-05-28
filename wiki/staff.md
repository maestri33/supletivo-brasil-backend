# staff

## Função

Serviço de **administração da plataforma** — o "boss da operação". Staff é
responsável por gerenciar a estrutura organizacional: cadastrar polos (hubs),
definir coordenadores, e supervisionar a saúde de todos os serviços via health
aggregation.

É o ponto central de governança operacional. Acesso restrito a papéis `admin`
e `staff`.

---

## Status

**Milestone 1 — spine.** Config, engine de banco e validação JWT/JWKS com gate
de role implementados. Modelos de domínio e endpoints de negócio entram nos
milestones 4/5.

---

## Estrutura

```
staff/
├── app/
│   ├── config.py         # Settings (pydantic-settings) — DATABASE_URL, JWT_BASE_URL
│   ├── db.py             # engine async, Base, NAMING_CONVENTION, get_session()
│   ├── dependencies.py   # validação JWT RS256 + gate admin/staff
│   └── exceptions.py     # DomainError, NotFound, Conflict, ValidationError
├── pyproject.toml
└── .env.example
```

---

## Modelo de dados

A definir nos milestones 4/5. Entidades planejadas:

- **StaffMember** — registro de membros da equipe administrativa
- **AuditLog** — log de ações administrativas (quem criou/alterou o quê)

---

## Endpoints

### Health/Status (planejados)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Healthcheck simples |
| GET | `/ready` | Readiness (testa conexão com DB) |
| GET | `/status` | Versão, ambiente, uptime |

### Negócio (planejados — milestones 4/5)

| Método | Rota | Tipo | Descrição |
|--------|------|------|-----------|
| POST | `/api/v1/admin/hubs` | Autenticado (admin/staff) | Criar polo |
| PATCH | `/api/v1/admin/hubs/{id}` | Autenticado (admin/staff) | Atualizar polo (ex.: definir coordenador) |
| DELETE | `/api/v1/admin/hubs/{id}` | Autenticado (admin/staff) | Remover polo |
| GET | `/api/v1/admin/health` | Autenticado (admin/staff) | Health aggregation de todos os serviços |
| POST | `/api/v1/admin/coordinators` | Autenticado (admin/staff) | Vincular coordenador a polo |

---

## Notas técnicas

- **Autenticação:** JWT RS256 validado contra JWKS do serviço `jwt`. Cache de
  5 minutos para evitar N requests por validação.
- **Roles:** `admin` e `staff` (configurável via `STAFF_ROLES` no `.env`).
- **Schema:** `staff` (próprio, conforme CONVENTION §4).
- **Engine:** async (`create_async_engine` + `asyncpg`).
- **Naming convention:** padrão do projeto (copiado de `address/app/db.py`).

---

## Dependências

- **jwt** — validação de token (JWKS)
- **hub** — cadastro e gestão de polos
- **coordinator** — definição de coordenadores (ainda não criado)
- **auth** — verificação de external_id e roles

---

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `staff` |
| `JWT_BASE_URL` | Base URL do serviço jwt | `http://jwt:80` |
| `STAFF_ROLES` | Roles aceitas (JSON) | `["admin","staff"]` |
| `SERVICE_NAME` | Nome do serviço | `staff` |
| `ENVIRONMENT` | Ambiente | `development` / `production` |
