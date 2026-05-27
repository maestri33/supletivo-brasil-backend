# CLAUDE.md — Memória e regras do microsserviço `commissions`

> Fonte da verdade para você (Claude Code) sobre o serviço `commissions`.
> Leia inteiro antes de agir. A convenção geral é `CONVENTION.md` (raiz);
> este arquivo só pode ser **mais restritivo**. Doc funcional completa:
> `wiki/commissions.md`.

---

## ⚠️ Status: NÃO CRIADO (Parte B — Sprint futuro)

Este serviço **ainda não tem código**. O diretório contém apenas stub:
`.env.example`, `Makefile` e este `CLAUDE.md`. O desenvolvimento está planejado
para sprints futuros da Parte B do PLANO_ADEQUACAO.md.

**Enquanto não houver código, este CLAUDE.md serve como especificação de
requisitos. Qdo o serviço for implementado, atualizar este arquivo com
informações reais da implementação.**

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: gerenciar **cálculo e pagamento de comissões** para promotores e
  coordenadores.
- **É caminho de dinheiro?** SIM. Comissões envolvem PIX via Asaas — exigem
  idempotência, rastreabilidade e tolerância a falhas.
- Schema `commissions`. PK = UUID.

## 2. Regras de negócio (planejadas)

1. **Comissão de lead:** ao concluir um lead (status `completed` no `lead`),
   gerar comissão para o promotor associado. Valor via ENV
   (`COMMISSION_LEAD_AMOUNT_CENTS`, padrão 10000 = R$100,00).
2. **Comissão de graduação:** ao postar foto do aluno com diploma (status
   `veteran` no `student`), gerar comissão para o coordenador do hub. Valor via
   ENV (`COMMISSION_GRADUATION_AMOUNT_CENTS`, padrão 5000 = R$50,00).
3. **Processamento semanal:** sexta-feira às 18h (America/Sao_Paulo):
   - Somar leads que geraram comissão na semana.
   - Se `count >= LEADS_BONUS_THRESHOLD` (ENV), adicionar
     `LEADS_BONUS_AMOUNT_CENTS` ao total.
   - Criar `payment_batch`, mudar status das comissões para `processed`.
   - Disparar pagamento PIX via integração Asaas.
4. **Idempotência:** webhook do Asaas atualiza status do batch. Sistema deve se
   recuperar de falhas sem duplicar pagamentos.
5. **Segurança de horário:** garantir que execução (America/Sao_Paulo) não gere
   processamento duplicado no fuso.

## 3. Stack (planejada)

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `commissions`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Modelo de dados (planejado)

### `commissions.commissions`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `recipient_external_id` | UUID | FK lógica → auth.users |
| `recipient_role` | enum | `promoter` ou `coordinator` |
| `source_type` | enum | `lead_completed` ou `student_graduated` |
| `source_external_id` | UUID | ID do lead ou student |
| `amount_cents` | int | Valor em centavos |
| `status` | enum | `pending`, `processed`, `paid`, `failed` |
| `payment_batch_id` | UUID | FK → payment_batches |
| `created_at` | timestamptz | Criação |
| `updated_at` | timestamptz | Última atualização |

### `commissions.payment_batches`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `week_of` | date | Semana de referência (sexta-feira) |
| `total_cents` | int | Soma das comissões |
| `bonus_cents` | int | Bônus (se meta atingida) |
| `status` | enum | `pending`, `processing`, `completed`, `failed` |
| `pix_transaction_id` | UUID | ID da transação Asaas |
| `created_at` | timestamptz | Criação |

## 5. Dependências

- **lead** — gera evento de lead concluído
- **student** — gera evento de aluno graduado (veteran)
- **promoter** — dados do promotor (recipient)
- **coordinator** — dados do coordenador (recipient)
- **asaas** — processamento de pagamento PIX
- **notify** — notificações de pagamento

## 6. O que NÃO fazer

- ❌ Processar comissão sem verificar idempotência (duplicar pagamento).
- ❌ Confiar em hora local do container — usar America/Sao_Paulo explícito.
- ❌ Fazer chamada PIX síncrona no request — processamento é sempre async/worker.
- ❌ Importar modelo de outro serviço.
- ❌ Commitar `.env` ou segredo.

---

**Antes de qualquer tarefa**, leia também `wiki/commissions.md` e
`CONVENTION.md` (raiz).
