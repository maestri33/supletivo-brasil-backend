# Guia de Contribuição — Backend Supletivo

> Alinhado com `CONVENTION.md` §15 e `.github/PULL_REQUEST_TEMPLATE.md`.

---

## 1. Política de Branches

| Branch | Propósito |
|---|---|
| `main` | Produção — código aprovado, testado, deployável |
| `chore/<desc>` | Padronização, refactor, docs, CI (sem mudança de comportamento) |
| `feat/<servico>-<desc>` | Feature nova em um serviço |
| `fix/<servico>-<desc>` | Correção de bug |

- **Nunca faça push direto em `main`.** Tudo entra via PR com revisão.
- 1 PR = 1 serviço/escopo fechado (regra de ouro do PLANO).

---

## 2. Guia de Commits

### 2.1 Estrutura da mensagem

```
<tipo>(<escopo>): <resumo curto em pt-br, até 72 chars>

[corpo opcional — o porquê, não o óbvio]
```

### 2.2 Tipos

| Tipo | Quando usar |
|---|---|
| `feat` | Funcionalidade nova |
| `fix` | Correção de bug |
| `refactor` | Reestruturação sem mudança de comportamento |
| `docs` | Só documentação (wiki, CLAUDE.md, README) |
| `test` | Adição/ajuste de testes |
| `chore` | Build, CI, lint, dependências |
| `migration` | Migração Alembic nova ou alterada |

### 2.3 Escopos

Nome do serviço (ex.: `auth`, `asaas`, `lead`) ou `infra` para docker-compose/CI.

Não empilhe múltiplos serviços num commit. Se mexeu em 2 serviços, são 2 commits (ou 2 PRs).

### 2.4 Exemplos

```
feat(lead): adiciona captura de lead via QR code PIX
fix(asaas): corrige idempotência do webhook de cobrança
refactor(auth): extrai lógica de validação para services/
docs(infra): cria CONTRIBUTING.md e PR template
migration(otp): adiciona coluna expires_at na tabela otp_codes
chore(address): migra psycopg2 para asyncpg
```

---

## 3. Fluxo de Trabalho

1. **Crie branch** a partir de `main`.
2. **Codifique** seguindo `CONVENTION.md` e o `CLAUDE.md` do serviço.
3. **Antes de commitar:** `ruff check` + `ruff format` limpos + `pytest` passando.
4. **Atualize docs:** `wiki/<servico>.md` (§15) e CLAUDE.md se relevante.
5. **Abra PR** usando o template `.github/PULL_REQUEST_TEMPLATE.md`.
6. **Solicite review** de outro agente/pessoa.
7. **Após aprovação**, faça squash-merge em `main`.

---

## 4. O que NUNCA fazer

- ❌ Push direto em `main`
- ❌ Commit de segredo (`.env`, chave, token)
- ❌ Commit com `ruff` sujo ou teste quebrado
- ❌ Mudança destrutiva sem aprovação humana (drop table, force push, etc.)
- ❌ Merge sem review

---

## 5. Links

| Recurso | Local |
|---|---|
| Convenção de código | `CONVENTION.md` |
| Template de PR | `.github/PULL_REQUEST_TEMPLATE.md` |
| Runbook | `wiki/RUNBOOK.md` |
| Plano de adequação | `wiki/PLANO_ADEQUACAO.md` |
| Docs por serviço | `wiki/<servico>.md` |
