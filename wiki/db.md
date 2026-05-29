# db — estratégia de banco compartilhado

> Fonte de verdade do **como** cada microsserviço se conecta a Postgres e Redis.
> Particularidades de uso (queries, modelos, migrações) ficam no `CLAUDE.md` /
> `README.md` de cada serviço.

---

## 1. Premissa

A `CONVENTION.md §1/§4` amarra a estratégia:

> "1 serviço = 1 schema Postgres" — e FK cross-schema via **shadow table read-only**
> (já em uso: `lead/app/db.py` declara shadow de `auth.users`).

FK cross-schema **só existe dentro do mesmo cluster Postgres**. Portanto:

- **1 cluster Postgres** compartilhado pela plataforma toda.
- **1 database** lógico: `v7m`.
- **1 schema por serviço**, nome = nome do serviço.
- **1 role/usuário por serviço**, owner do próprio schema.
- Cross-schema só via `GRANT USAGE` + `GRANT SELECT` específico (sem importar
  model alheio — §4 e §6).

A separação por role enforça §6 (fronteira) **no próprio banco**: se `lead`
tentar `INSERT` em `auth.users`, o PG nega. Não depende da disciplina do dev.

---

## 2. Infra

| Item | Valor |
|---|---|
| Host | CT 2100 (`db` no tailnet) |
| IP | `10.1.20.100` (vmbr1) — também acessível via `100.x.y.z` (tailnet) |
| Porta PG | `5432` |
| Porta Redis | `6379` |
| Versão PG | 18 |
| Versão Redis | 7 |
| Auth | `scram-sha-256` (host) |
| Acesso liberado em `pg_hba.conf` | `10.1.20.0/24` e `100.64.0.0/10` |
| Database | `v7m` (compartilhado pelos micros — Evolution fica em DB próprio ao lado) |
| TLS | não (rede interna/tailnet) — não expor 5432 fora |

Onde ficam os secrets reais:

- **Senhas dos roles** → `/root/v7m-db-creds.env` no CT 2100 (chmod 600, root-only).
- **Script de provisionamento** → `/root/v7m-db-provision.sh` no CT 2100
  (idempotente, lê do creds file). Aplicar com `pct exec 2100 -- /root/v7m-db-provision.sh`.
- **Buscar senha de um serviço** (do dev box ou de outro host com tailnet):
  ```bash
  pct exec 2100 -- bash -c 'grep V7M_AUTH_DB_PASSWORD /root/v7m-db-creds.env'
  ```
  Substituir `AUTH` pelo nome do serviço em maiúsculas.

> **Nunca colar senha em arquivo versionado.** Este wiki vai pro GitHub. Senha
> só em `.env` local (já no `.gitignore`) ou em secret manager.

---

## 3. Template de conexão

### Postgres (SQLAlchemy 2.0 + asyncpg)

```env
DATABASE_URL=postgresql+asyncpg://<svc>:<senha>@10.1.20.100:5432/v7m
DATABASE_SCHEMA=<svc>
```

- `<svc>` = nome do serviço (`auth`, `lead`, `address`, …).
- O role tem `search_path = <svc>, public` setado por `ALTER ROLE` — então
  consultas a tabelas do próprio schema funcionam sem qualificar.
- O `MetaData(schema=settings.database_schema)` (CONVENTION §4) cuida do resto.

### Redis (cache/efêmero — §2)

```env
REDIS_URL=redis://10.1.20.100:6379/<n>
```

- Sem senha (Redis no 2100 não está atrás de AUTH — só rede interna).
- `<n>` = número de DB Redis alocado abaixo.

---

## 4. Alocação por serviço

Serviços com `app/db.py` em `models/`-style (SQLAlchemy async). Todos têm
schema + role homônimos. Coluna **Shadow** mostra de quais schemas alheios
o serviço lê via shadow table (precisa de `USAGE + SELECT`).

| Serviço | Schema PG | Role | Redis DB | Shadow | Observações |
|---|---|---|---|---|---|
| address | `address` | `address` | — | `auth.users` | |
| asaas | `asaas` | `asaas` | — | — | `external_id` lógico, sem FK |
| auth | `auth` | `auth` | `0` | — | **Migra primeiro** (todos referenciam) |
| candidate | `candidate` | `candidate` | — | — | `external_id` lógico |
| documents | `documents` | `documents` | — | — | Usa Tortoise ORM (anomalia §2) |
| enrollment | `enrollment` | `enrollment` | — | `auth.users` | |
| fees | `fees` | `fees` | — | — | |
| hub | `hub` | `hub` | — | — | `external_id` para address/coordinator |
| infinitepay | `infinitepay` | `infinitepay` | — | `auth.users` | |
| lead | `lead` | `lead` | — | `auth.users` | App-modelo |
| notify | `notify` | `notify` | `2` | `auth.users` | Hoje em sqlite — migrar |
| otp | `otp` | `otp` | `1` | `auth.users` | OTP code também em Redis |
| profiles | `profiles` | `profiles` | — | `auth.users` | |
| promoter | `promoter` | `promoter` | — | — | `external_id` lógico |
| roles | `roles` | `roles` | — | `auth.users` | |
| student | `student` | `student` | — | `auth.users` | |
| training | `training` | `training` | — | — | `external_id` lógico no M2 |

DBs Redis 3–15 reservados pra novos serviços (alocar incrementalmente).

Serviços **sem `app/db.py`** (stateless ou ainda não modelados): `ai`,
`commissions`, `coordinator`, `jwt`, `staff`. Quando ganharem banco, criar
schema + role seguindo a tabela acima e atualizar o script de provisionamento.

---

## 5. Como adicionar um serviço novo

1. Gerar senha:
   ```bash
   pct exec 2100 -- bash -c 'openssl rand -base64 24 | tr -d "/+=" | cut -c1-32'
   ```
2. Adicionar ao `/root/v7m-db-creds.env` no 2100 como `V7M_<NOME>_DB_PASSWORD=...`.
3. Adicionar o nome do serviço ao array `SERVICES` em `/root/v7m-db-provision.sh`.
4. Se o serviço usa shadow `auth.users`, adicionar também ao array `SHADOW_AUTH`.
5. Rodar `pct exec 2100 -- /root/v7m-db-provision.sh` (idempotente).
6. Popular o `.env` do serviço com o `DATABASE_URL`/`DATABASE_SCHEMA` do §3.
7. `alembic upgrade head` na primeira migração.

---

## 6. Ordem de migração inicial

Como há FK cross-schema apontando pra `auth.users`, **o auth migra primeiro.**
Depois, qualquer ordem funciona (os demais shadow tables só leem auth).

```
auth → [address, enrollment, infinitepay, lead, notify, otp, profiles, roles, student] em paralelo
       [asaas, candidate, documents, fees, hub, promoter, training] em paralelo
```

Quando o `auth` cria a tabela `users` pela primeira vez, conceder retroativo:

```sql
GRANT SELECT ON auth.users TO address, enrollment, infinitepay, lead,
                              notify, otp, profiles, roles, student;
```

O script de provisionamento já configura `ALTER DEFAULT PRIVILEGES` no role
`auth`, então tabelas **futuras** criadas pelo auth herdam SELECT pros consumers
automaticamente. O `GRANT` acima só é necessário pra tabelas que já existiam
antes do `ALTER DEFAULT PRIVILEGES` (na primeira passagem, é o caso).

---

## 7. Dev local vs. produção

| Cenário | Onde fica o Postgres |
|---|---|
| Teste E2E local do serviço | Postgres efêmero do próprio compose do serviço (já é o padrão hoje) |
| Dev integrado no [ct-220-workspace] | Apontar `.env` pro 10.1.20.100 com a senha real |
| Produção (compose por serviço no host de prod) | Mesmo URL, mesmo cluster |

Não precisa de Postgres separado pra dev integrado e prod — o cluster é o
mesmo, isolamento é por database/role/schema. Se quiser dev isolado de prod,
criar um database `v7m_dev` no mesmo cluster (mesmos roles, schemas paralelos).

---

## 8. Backup / DR

- Backup do cluster pg18 é responsabilidade do CT 2100 (cobre `v7m` + `evolution`
  no mesmo dump físico).
- DR via réplica streaming pro [pareamento-pve-home] está no roadmap, ainda
  não configurado.

---

## 9. Observabilidade

- `pgweb` no 2100 (porta 8081) — UI web pra inspecionar schemas/queries.
- `pg_stat_activity` por role mostra quem está fazendo o quê — usar o nome do
  role na coluna `usename` pra atribuir queries ao serviço.

---

## 10. Não faça

- ❌ Compartilhar uma senha única entre serviços ("v7m" superuser pra todo
  mundo). Mata o §6 (fronteira) e amplia blast radius.
- ❌ Importar `model` de outro serviço pra fazer JOIN nativo. Use shadow table
  (§4) ou chamada HTTP.
- ❌ Criar database separado por serviço. Mata FK cross-schema (§4).
- ❌ Subir Postgres no compose de cada serviço em produção (24 clusters,
  zero economia de cache, sem cross-schema FK).
- ❌ Commitar `.env` com senha real (já está no `.gitignore`, manter assim).
- ❌ Expor 5432/6379 fora da rede interna (tailnet + vmbr1 já é o suficiente).
