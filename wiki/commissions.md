# commissions

## Função

Gerencia o cálculo e pagamento de **comissões** para promotores e coordenadores. Cada vez que um lead é concluído, uma comissão é gerada para o promotor relacionado. Quando um aluno conclui o ciclo (foto com diploma), uma comissão vai para o coordenador do hub. Toda sexta-feira às 18h (America/Sao_Paulo), as comissões pendentes são processadas: soma total, bônus se atingir meta de leads (ENV), e dispara pagamento via PIX (integração Asaas).

---

## Status

**Não criado (Parte B / Sprint futuro).** Apenas descrição de requisitos existe no `TODO`.

---

## Modelo de dados (planejado)

### Tabela `commissions.commissions`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `recipient_external_id` | UUID | FK lógica para auth.users (promotor ou coordenador) |
| `recipient_role` | enum | `promoter` ou `coordinator` |
| `source_type` | enum | `lead_completed` ou `student_graduated` |
| `source_external_id` | UUID | ID do lead ou student que gerou a comissão |
| `amount_cents` | int | Valor em centavos (configurado via ENV) |
| `status` | enum | `pending`, `processed`, `paid`, `failed` |
| `payment_batch_id` | UUID | Referência ao batch de pagamento semanal |
| `created_at` | timestamptz | Criação |
| `updated_at` | timestamptz | Última atualização |

### Tabela `commissions.payment_batches`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `week_of` | date | Semana de referência (sexta-feira) |
| `total_cents` | int | Soma das comissões do batch |
| `bonus_cents` | int | Bônus aplicado (se meta atingida) |
| `status` | enum | `pending`, `processing`, `completed`, `failed` |
| `pix_transaction_id` | UUID | ID da transação Asaas |
| `created_at` | timestamptz | Criação |

---

## Regras de negócio

1. **Comissão de lead:** ao concluir um lead (status `completed` no serviço `lead`), gerar comissão para o promotor associado. Valor configurado em ENV (padrão: R$100,00).
2. **Comissão de graduação:** ao postar foto do aluno com diploma (status `veteran` no serviço `student`), gerar comissão para o coordenador do hub. Valor configurado em ENV (padrão: R$50,00).
3. **Processamento semanal:** sexta-feira às 18h (America/Sao_Paulo):
   - Contar leads que geraram comissão na semana.
   - Se `count >= LEADS_BONUS_THRESHOLD` (ENV), adicionar `LEADS_BONUS_AMOUNT` (ENV) ao total.
   - Criar `payment_batch`, mudar status das comissões para `processed`.
   - Disparar pagamento PIX via integração Asaas.
4. **Idempotência:** webhook do Asaas atualiza status do batch. Sistema deve se recuperar de falhas sem duplicar pagamentos.
5. **Segurança contra reexecução:** garantir que horário de execução (America/Sao_Paulo) não gere processamento duplicado.

---

## Endpoints (planejados)

### Desmilitarizados (interno)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/demilitarized/commissions` | Lista comissões (filtro por status, período, recipient) |
| GET | `/api/v1/demilitarized/commissions/{id}` | Detalhe de uma comissão |
| GET | `/api/v1/demilitarized/batches` | Lista batches de pagamento |
| GET | `/api/v1/demilitarized/batches/{id}` | Detalhe de um batch |
| POST | `/api/v1/demilitarized/commissions/trigger` | Força processamento (admin/debug) |

---

## Dependências

- **lead** — gera evento de lead concluído
- **student** — gera evento de aluno graduado (veteran)
- **promoter** — dados do promotor (recipient)
- **coordinator** — dados do coordenador (recipient)
- **asaas** — processamento de pagamento PIX

---

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `COMMISSION_LEAD_AMOUNT_CENTS` | Valor da comissão por lead (centavos) | `10000` |
| `COMMISSION_GRADUATION_AMOUNT_CENTS` | Valor da comissão por graduação (centavos) | `5000` |
| `LEADS_BONUS_THRESHOLD` | Nº mínimo de leads para bônus semanal | `10` |
| `LEADS_BONUS_AMOUNT_CENTS` | Valor do bônus semanal (centavos) | `5000` |
| `WEEKLY_CRON_HOUR` | Hora do processamento semanal (TZ) | `18` |
| `TZ` | Timezone | `America/Sao_Paulo` |
