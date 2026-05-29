# Visão Consolidada — Supletivo (a INTENÇÃO do dono)

> Fonte: os **13 `TODO`** (palavras do dono — ignorei o header "SUPERSEDED→PRD" que
> a IA enfiou) **+** a conversa de 28–29/05. Isto é a **régua** (o que ele QUER).
> O código se mede contra isto — não o contrário. Auditoria de "o que já tem feito"
> vem DEPOIS. Valores em **`.env`** (config), não fixos.

---

## A ESPINHA: dois funis paralelos (a "digivolução" de papéis — definida no `roles`)

### Funil do ALUNO (entra dinheiro)
`lead → (PAGOU) → enrollment → student → (conclui) → student+veteran`
- **lead**: captado pela URL do promotor (`/ref=external_id`). Paga.
- **enrollment**: ao pagar, vincula ao **hub do promotor que indicou**. Coleta:
  profile, endereço, **document/RG (obrigatório)**, **dados educacionais — CRÍTICO:
  último ano que estudou, quando, qual escola**, **selfie** (validação tipo
  assinatura de contrato, mesma lógica do candidato). Progride conforme posta;
  tudo postado → status **aguardando liberação**; coordenador do hub é **notificado**;
  coordenador insere dados de acesso à plataforma → enrollment concluído → vira **student**.
- **student → veteran**: conclui o curso; coordenador **posta foto do aluno com o
  diploma** → fecha o ciclo, vira **veteran** (→ gera comissão pro coordenador).

### Funil do PROMOTOR (motor de captação)
`candidate → training → promoter → (opcional) + coordinator`
- **candidate** (segue a MESMA lógica/passo-a-passo do lead, requisitos diferentes;
  reusar lógica, não duplicar):
  1. `POST /register` → phone, cpf, hub (`HUB_DEFAULT` no `.env` se não informado)
  2. `/profile` (cpf já puxa nome etc.)
  3. `/address` (cep puxa dados; não duplicar lógica)
  4. documents: **RG ou CNH**
  5. **cadastro chave Pix + validar no Asaas** (lógica já existe lá)
  6. **selfie REAL** (validação tipo assinatura) → tudo ok → conclui candidato →
     **update role → training**
- **training** (tipo LMS): matérias (1 vídeo + 1 foto + 1 texto + 1 questão c/
  resposta esperada). Aluno envia resposta → **IA (app `ai`, DeepSeek) corrige
  assíncrono**: nota 0–10 + justificativa; **≥6 = aprovado** (senão reenvia). Todas
  aprovadas → **aguardando entrevista com o coordenador** → coordenador
  `post/external_id` aprova/rejeita (rejeita = texto motivo) → aprovado → **promoter**.
- **promoter**: vinculado a um hub. Gere seus leads/comissões. **O MAIS IMPORTANTE:
  a URL `landing/ref=external_id`** pra captar lead.
- **coordinator** = promoter + funções administrativas do polo (ver abaixo).

---

## O MOTOR DE DINHEIRO — `commissions` (3 ganhos, pagos SÓ no lote semanal)
- **Comissão direta**: cada lead que **PAGA** → comissão (`.env`, ref R$100) pro
  **promotor que indicou** (via `ref`).
- **Comissão de coordenador**: cada **student que vira veteran** → comissão (`.env`,
  ref R$50) pro **coordenador do hub**.
- **Bônus**: promotor com **≥5 indicações na semana** → **flat** (`.env`, ref R$500;
  não escala — 4 não ganha, 100 ganha o mesmo).
- **Lote: sexta 18:00 America/Sao_Paulo** → agrega comissões+bônus **por beneficiário**
  → **1 pagamento Pix por pessoa** → muda status pra `processed` → em outra tabela cria
  a solicitação de pagamento.
- **`externalReference` = `{ordinal-sexta 1–4}_{MM}_{AAAA}_{external_id}`** grudado em
  TODAS as comissões/bônus do pagamento = **idempotência de payout** (tem ref = já
  processado).
- **Fila persistente** até receber o `id` do Asaas; **sem saldo → ESPERA na fila**.
  Pós-id: **fonte de verdade = status via webhook OU consulta**. Segurança de fuso
  (não repetir). Asaas já coeso (Pix in/out).

---

## SERVIÇOS DE APOIO
- **auth** — **fonte de verdade** da plataforma. Ao criar usuário, **auto-cria** Profile
  + Documents + contato (notify) + endereço (a maioria com null). **JAMAIS dois usuários
  com CPF/phone/email iguais ou falsos.**
- **roles** — máquina de papéis (lead, candidate, training, promoter, student,
  coordinator, staff, admin). **Lista de papéis no `.env`, não em DB.**
- **documents** — ao criar usuário, cria um document (external_id) + todos os docs
  null relacionados: CNH, RG, certidão (nascimento/casamento/etc — 1 por document),
  serviço militar (só homens, mas criar). Espaço pra fotos.
- **hub** (polo) — criar **um default** primeiro. Tem endereço + **marca** (Estácio/
  Wyden/outra) + coordenador (external_id). Contém seus promotores (candidato/training/
  promotor) e alunos (lead/enrollment/student-veteran).
- **fees** — taxas de matrícula via Asaas: coordenador faz **2 pagamentos por QR-code
  (à vista + agendamento — já no asaas)**. Relacionado ao student; status segue o Asaas.
  **Só o coordenador acessa.** **Acesso à plataforma só libera quando a 1ª parte é paga.**
- **staff** — o **boss** da operação. Consome quase todas as APIs desmilitarizadas. **Só
  staff cadastra hub e define coordenador.** Bom: ver a saúde de cada serviço.
- **coordinator** (= promoter + admin do polo): aprova quem terminou o training →
  vira promoter; envia docs do aluno p/ instituição; insere dados de acesso; paga +
  cadastra taxas; aplica/corrige/posta prova; envia docs; posta histórico + diploma;
  **posta foto do aluno com diploma → veteran**. Pode deixar de ser coordenador.
- **profiles, address, otp, notify, jwt** — apoio. (otp: candidato a descomissionar;
  só "conectar no postgres".)
- **asaas** (Pix in/out, validado) / **infinitepay** / **ai** (DeepSeek p/ correção
  do training + recibo/fraude).

---

## LEIS DE ARQUITETURA (do dono — vencem delírio)
1. **1 `.env` central** (já é assim — compose usa só o root). 2. **1 Postgres** pra todos.
3. Fotos → **`media/`** do app. 4. **Docs/README só no FIM** (depois de funcionar e
   aprovar; um `app.md` por app explicando função+integrações). 5. **`.env.example` só
   na produção**. 6. **wiki: dropado**.
- **Convenção de endpoints (3 camadas):** `public/` (expostos ao mundo), `authenticated/`
  (exigem JWT), `demilitarized/` (só dentro da plataforma — listar, filtrar por hub, etc).
- **Reusar, não duplicar** lógica (cpf puxa nome, cep puxa endereço, selfie, validação
  de Pix no asaas, padrão do lead). **Seguir convenção já estabelecida.**

---

## PRÓXIMO PASSO
Com ISTO como régua → **auditar o código** serviço por serviço: o que está PRONTO /
STUB / DELÍRIO / FALTANDO **vs esta visão**. (Já sabemos: o payout de `commissions` é
delírio — paga placeholder, não faz isto.)
