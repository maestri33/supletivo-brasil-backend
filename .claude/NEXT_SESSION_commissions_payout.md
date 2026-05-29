# Próxima sessão — Payout semanal de comissões (AUDITAR antes de codar)

> Handoff escrito 2026-05-29. Sessão anterior ficou cara ($349) e o gate de custo
> passou a barrar agentes. **Abra uma sessão NOVA** (zera contador + contexto limpo)
> e comece pela AUDITORIA abaixo. NÃO comece codando.

## Regra de ouro do fundador
- "Já planejei tudo nos mínimos detalhes na mente." → **evitar duplicação** e os
  "delírios de IA espalhados". Antes de qualquer código: **ver o que já existe e se
  funciona**, reusar o que dá.
- **Valores de comissão são CONFIG** (vamos baixar pra testar com valor pequeno; a
  **lógica** é o que importa, não o número).
- Nada em produção ainda. Dev usa Asaas/InfinitePay **reais** (sem sandbox) → teste
  end-to-end gera cobrança/payout real (pequeno). Conta Asaas de prod é reserva/test.

## DESENHO TRAVADO (fonte de verdade — do fundador)
**3 tipos de ganho, TODOS pagos só pelo lote semanal:**
1. **Comissão por indicação direta** — valor fixo por lead indicado que **PAGA**
   (entra na matrícula). Atribuição via `ref` = `external_id` do promotor, capturado
   no lead. (captura do ref no lead = pré-requisito, "implementa depois")
2. **Bônus** — **FLAT** se o promotor fez **≥5 indicações** na semana
   (sex 18h → sex 18h). NÃO escala: 4 não ganha; 100 ganha o mesmo flat.
3. **Comissão de coordenador de hub** — valor **menor**, por aluno que **CONCLUI**
   (vira "veterano" = pega diploma + posta foto com ele).

Valores de referência (CONFIG, baixar p/ teste): comissão **R$100**/aluno; bônus
**R$500** (≥5); coordenador **R$50**/concluído. Preço do aluno: inauguração **R$999
Pix** ou **12×99 cartão**; oficial ~**R$1600** (1 salário mínimo). Custo/aluno ~R$400.

**Fechamento (cron sexta 18:00 America/Sao_Paulo):**
- agrega comissões da semana + bônus + comissões de coordenador, **por beneficiário**
  → **1 pagamento único** pro Pix dele.
- **`externalReference` = `{ordinal-da-sexta-no-mês 1-4}_{MM}_{AAAA}_{external_id}`**,
  grudado em **TODAS** as comissões/bônus daquele pagamento. **Se tem
  `externalReference` = já processado** (idempotência de PAYOUT). Complementa a
  idempotência de CRIAÇÃO por evento que o PRD já tem (`source_type+source_external_id`).
- pagamento entra em **FILA PERSISTENTE até receber o `id` do Asaas**. Conta **sem
  saldo → ESPERA na fila** até ter (não falha).
- pós-id: **fonte de verdade = status via webhook do Asaas OU consulta ativa**.
- Payout = Asaas **PIX-out/transfer** ("asaas tem tudo isso").
- **Pix do promotor: guardar em `profiles`.** Validado (válido + pertence à pessoa —
  já desenvolvido c/ Asaas) no **último passo do candidato antes de virar `training`**
  (candidato→training espelha lead→matrícula).
- Fundador se cadastra primeiro: será o **promotor default + coordenador de hub default**.

## PRD `commissions.prd.md` — estrutura OK, NÚMEROS errados (corrigir)
Estrutura certa (lote semanal idempotente, 3 tipos, status `pending→processed→paid`,
"rodar 2× não duplica"). Placeholders a corrigir:
- `PROMOTER_COMMISSION_CENTS=100` (R$1,00) → tornar **config** (ref R$100 = 10000c).
- `BONUS_THRESHOLD_COUNT=10` → **5**.
- Bônus "por lead R$0,50" → **FLAT** (ref R$500). **Muda a lógica, não só o número.**
- Coordenador: definir valor (ref R$50).

## 1ª AÇÃO na sessão nova — AUDITORIA (barata: grep direcionado, não ler tudo)
Mapear o que já existe vs o desenho acima, pra não duplicar. Responder com tabela
`[elemento → PRONTO/STUB/FALTANDO/DUPLICADO → arquivo:linha]`:
1. `commissions/app`: models (Commission, PaymentBatch) + services
   (commission_service, payment_batch_service, commissions.py, worker.py).
2. `externalReference` — existe? formato bate? onde gera/checa?
3. Fila persistente — espera-id-Asaas + espera-saldo, ou stub/fire-and-forget?
4. `asaas` — tem cliente/endpoint de **transfer/PIX-out** (payout)? commissions plugado?
5. cron sexta-18h — onde? timezone correto?
6. **DUPLICAÇÃO** — comparar fila/worker do commissions com
   `infinitepay/app/workers/outbound_queue.py` (fila persistente + claim atômico +
   retry — **reusar esse padrão, não reimplementar**) e qualquer outbound do asaas.

## Validação final (antes de prod): ensaio money com valor pequeno
End-to-end real, valor mínimo, contas/Pix que VOCÊ controla nas 2 pontas (aluno paga,
promotor recebe). Provar no lote: **idempotência** (rodar 2× não paga dobrado),
**falha parcial** (1 Pix falha → resto segue?), **acumulação certa**, **gatilho**.
