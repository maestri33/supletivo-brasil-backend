# Estado & Plano — Projeto Supletivo (2026-05-29)

> Consolidação da sessão. Quatro partes: **(1)** o que fizemos hoje · **(2)** o que
> percebi do que vocês têm · **(3)** o que você me explicou (seu plano, já na sua
> cabeça) · **(4)** o que falta descobrir pra traçar o plano.
> Doc-irmão (detalhe do payout): `NEXT_SESSION_commissions_payout.md`.

---

## 1. O QUE FIZEMOS HOJE

**Começou como "estratégia de CI/CD" e virou raio-x do projeto.**

### CI/CD — Fase 0 (entregue, no `master`)
- **Achado-raiz:** o `ci.yml` era **YAML inválido** (passo alembic com `: ` dentro de
  `"skip: no alembic"`). O GitHub rejeitava o arquivo → **0 jobs rodaram na história
  do repo, em nenhum branch** (runs morriam em 0s = "workflow file issue"). O CI nunca
  funcionou. E o `master` não tinha workflow + estava **66 commits atrás** da branch
  ativa `fix/lead-review-2026-05-28`.
- **Consertado e no master** (PR #3 mergeado): YAML válido, gatilho `main`→`master`,
  **e2e money-path DESARMADO** (`if: false` — ele subia o `lead` real → Asaas/InfinitePay
  reais → risco de cobrança PIX de verdade), gate de cobertura focado no money-path
  @60% (lead/asaas/infinitepay/candidate/training/fees — todos medidos ≥65%).
- **`master` protegido (leve):** PR obrigatório (auto-merge, 0 aprovações),
  force-push/deleção bloqueados, escape-hatch de admin (você nunca trava), **não exige
  verde ainda**.

### Corrupção de código encontrada e recuperada
- O commit **`bccfb5d`** colou conteúdo com **número de linha (gutter)** dentro de
  **7 `app/main.py`** (otp, notify, hub, enrollment, jwt, profiles, address) →
  **não compilavam, serviços não subiam.**
- **Recuperados todos na branch** `fix/lead-review`: 6 restaurados do histórico git
  (commit `04a285f`); `notify` veio da sua WIP, que já estava boa + tinha o middleware
  de security headers (commit `e8e914f`). Sua WIP (43 arquivos) ficou intacta.

### Sustos descartados (boas notícias)
- **Webhook de pagamento ESTÁ seguro** — o `webhook_security.py` existe e está plugado
  (IP allow-list + HMAC). A "deleção" do início da sessão tinha sido revertida.
- **Endpoint Evolution (notify) estava certo** o tempo todo (`/instance/fetchInstances`
  em `whatsapp.py`) — nada perdido.
- **GitGuardian:** os 6 findings eram chave do WhatsApp Evolution + chaves dev do
  Infisical (IP privado, risco baixo). **NÃO vazou** Asaas/InfinitePay/CPFHub/SMTP/JWT.
  `master` limpo.

### Tentativa de deixar o PR #5 (branch verde) 100% verde — PARCIAL
- Lint baseline (50 `noqa`, regras E402/E501/F841 etc.), conserto do `test/lead`
  (faltava env dummy no passo alembic). **Sobraram falhas só-no-CI** que não consegui
  diagnosticar (o `gh` não devolve os logs). **PR #5 não foi mergeado.**

### Virada de foco
- Concluímos: **parar de polir CI** (não fatura) e ir pro **caminho do dinheiro**.
- **Travamos por inteiro o desenho do payout semanal de comissões** (ver parte 3).

**Custo da sessão: ~$350.** Lição honesta: foi caro pro seu momento, e parte foi eu
indo fundo demais em CI. A próxima sessão começa **barata e pelo dinheiro**.

---

## 2. O QUE PERCEBI SOBRE O QUE VOCÊS TÊM (leitura honesta)

- **Arquitetura sólida:** ~22 microserviços FastAPI (SQLAlchemy 2 async + asyncpg +
  Alembic + Pydantic v2 + structlog), **cada um com seu schema** no Postgres central,
  comunicação por HTTP, referência cruzada por **`external_id` (UUID opaco)**. Cada
  serviço tem seu `.claude/CLAUDE.md` bem-feito (ex.: infinitepay deixa explícito
  "caminho do dinheiro é atômico"). **Isso é maduro — não é bagunça.**
- **Nada em produção ainda.** Tudo é dev. E **dev bate em Asaas/InfinitePay/CPFHub
  REAIS** (sem sandbox) → qualquer teste de ponta a ponta mexe dinheiro real (pequeno).
- **`master` está velho** (66 commits atrás); o trabalho real vive nas branches.
- **O que está validado/funcionando:** pagamento Asaas (Pix in/out, cobrança,
  security-validator), app do aluno (funil completo), training M1–M4.
- **O que está construído mas é risco:** o **payout de comissão é scaffold** — o
  `payment_batch_service.py` + `worker.py` estão a **0% de teste**. É o código menos
  testado e o que mexe mais dinheiro. **Não confiar nele ainda.**
- **5 serviços com testes reais quebrados** (address, auth, enrollment, profiles,
  staff) — em quarentena no CI; são dívida a triar.
- **Padrão de ouro a REUSAR:** o `infinitepay/app/workers/outbound_queue.py` —
  **fila persistente + claim atômico + retry**. É exatamente o padrão que o payout de
  comissão precisa. **Não reimplementar — reusar.**
- **O problema dos "delírios de IA":** existem PRDs e código gerados por sessões
  anteriores de IA que **não batem com o seu plano mental** — ex.: o
  `commissions.prd.md` tem a estrutura certa mas **números placeholder errados**
  (comissão R$1,00 em vez de R$100; bônus modelado "por lead" em vez de **flat**;
  threshold 10 em vez de 5). Por isso a regra: **auditar antes de codar.**

---

## 3. O QUE VOCÊ ME EXPLICOU (seu plano — você já tem tudo na cabeça)

### Contexto do negócio
- Você tem **o produto na mão**. Tem **contratos de polos** ("uma cagada", parados).
  **Dívida grande.** Está **pré-lançamento**.
- **Preço:** inauguração **R$999 (Pix)** ou **12× R$99 (cartão)**; oficial depois
  ~**R$1.600** (1 salário mínimo). **Custo médio por aluno ~R$400.** Preço de
  inauguração vale só enquanto há poucos promotores.
- Você vai **se cadastrar primeiro** — será o **promotor default** e **coordenador de
  hub default**.

### 3 frentes
1. **Aluno** — traz o $$. Funil `lead → matrícula → aluno`. Paga.
2. **Promotor** — busca aluno e ganha comissão. Funil `candidato → treinamento →
   promotor`. (espelha o do aluno: candidato vai pro treinamento como lead vai pra
   matrícula.)
3. **Coordenador de hub** — parte burocrática; e alguns promotores **também** são
   coordenadores.

### Os 3 tipos de ganho (todos pagos SÓ pelo lote semanal)
1. **Comissão por indicação direta** — valor fixo por lead indicado que **PAGA**
   (entra na matrícula). Atribuição via **`ref` = `external_id` do promotor**,
   capturado no lead. _(captura do ref no lead = pré-requisito, "implementa depois")_
2. **Bônus** — **FLAT** se o promotor fez **≥5 indicações** na semana
   (sex 18h → sex 18h). **Não escala:** 4 não ganha; 100 ganha o mesmo flat.
3. **Comissão de coordenador de hub** — valor **menor**, por aluno que **CONCLUI**
   (vira "veterano" = pega diploma + posta foto com ele).

_Valores de referência (são **CONFIG** — baixar pra testar): comissão **R$100**/aluno;
bônus **R$500** (≥5); coordenador **R$50**/concluído. A **lógica** importa, não o número._

### O fechamento semanal (cron sexta 18:00 America/Sao_Paulo)
1. Conta indicações da semana por promotor → bateu o alvo (≥5) → lança bônus.
2. Soma comissões da semana **+ bônus + comissões de coordenador**, **por beneficiário**.
3. Cria **1 pagamento único** por pessoa → o **Pix dela**.
4. Esse pagamento carrega um **`externalReference` =
   `{ordinal-da-sexta-no-mês 1–4}_{MM}_{AAAA}_{external_id}`**, **grudado em TODAS** as
   comissões/bônus que ele engloba. **Se tem `externalReference` = já foi processado**
   (trava de idempotência do payout).
5. O pagamento entra numa **fila persistente até receber o `id` do Asaas**. Se a conta
   **não tem saldo, ESPERA na fila** até ter (não falha).
6. A partir do `id`, a **fonte de verdade é o status** — via **webhook do Asaas OU
   consulta** ativa.
- **Payout = Asaas PIX-out/transfer** ("asaas tem tudo isso").
- **Pix do promotor:** guardado em **`profiles`**; validado (é válido + pertence à
  pessoa — já desenvolvido com Asaas) no **último passo do candidato antes de virar
  `training`**.

**Resumo:** é o padrão certo de dinheiro sério — idempotência por chave + fila
persistente + status-como-verdade. É praticamente o `outbound_queue` do infinitepay.

---

## 4. O QUE PRECISAMOS DESCOBRIR AGORA (pra traçar o plano)

**A peça que falta é a AUDITORIA** — bater o desenho (parte 3) contra o que já existe
no código, pra não duplicar nem confiar em scaffold. Perguntas concretas a responder:

1. **Commissions hoje:** os models (`Commission`, `PaymentBatch`) e services
   (`commission_service`, `payment_batch_service`, `commissions.py`, `worker.py`)
   implementam o desenho, ou são **stub/scaffold**? O quê está pronto vs faltando?
2. **`externalReference`:** existe? o formato bate com
   `{ordinal-sexta}_{MM}_{AAAA}_{external_id}`? (você acha que "o app que faz só isso"
   já implementou — confirmar onde.)
3. **Fila persistente:** existe? espera-pelo-id-do-Asaas **e** espera-por-saldo, ou é
   fire-and-forget?
4. **Asaas payout:** o serviço `asaas` expõe **transfer/PIX-out**? `commissions` está
   plugado nele ou é stub?
5. **Cron sexta-18h:** existe? timezone certo (America/Sao_Paulo)?
6. **Atribuição (`ref`):** o `lead` já captura/grava qual promotor indicou? (sem isso,
   nenhuma comissão dispara — é pré-requisito do funil de promotor.)
7. **Evento "veterano":** como o sistema sabe que o aluno concluiu (diploma + foto)?
   é o gatilho da comissão de coordenador.
8. **Validação de Pix no funil:** o passo candidato→training (valida Pix + dono) está
   implementado? grava o Pix em `profiles`?
9. **DUPLICAÇÃO:** o que dá pra **reusar** do `infinitepay/app/workers/outbound_queue.py`
   em vez de reescrever?

**Depois da auditoria** (e só depois), o plano se desenha sozinho em 3 movimentos:
- **A.** Fechar os buracos do payout reusando o padrão de fila (idempotência +
  espera-saldo + status-como-verdade), com os valores em config.
- **B.** **Ensaio "money" de ponta a ponta com valor pequeno** (contas/Pix que você
  controla nas 2 pontas): aluno paga → matrícula → comissão lançada → lote sexta →
  payout pro promotor. Provar: **idempotência** (rodar 2× não paga dobrado),
  **falha parcial**, **acumulação certa**, **gatilho**.
- **C.** Plano de subida pra produção (deploy seguro, backup, os fixes dev→prod).

---

## PRÓXIMO PASSO CONCRETO
**Sessão nova** (zera custo + contexto limpo) →
*"lê `.claude/ESTADO_E_PLANO_2026-05-29.md` e `.claude/NEXT_SESSION_commissions_payout.md`,
e faz a auditoria do payout — barato, grep, sem ler o repo todo"* →
sai o mapa **pronto/stub/faltando/duplicado** → aí traçamos o plano A/B/C.
