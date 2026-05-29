# AUDITORIA DOS 22 APPS — 2026-05-29

Mapa unico cruzando o codigo de cada app com a intencao do dono (VISAO_CONSOLIDADA + TODOs + CONVENTION).
Base: 22 relatorios de auditoria (1 por app). Sem floreio — o que esta pronto, o que e delirio, o que falta.

---

## 1. TABELA GERAL

| app | estado | veredito (1 linha) |
|---|---|---|
| **lead** | REAL | App mais maduro: funil completo, PIX+cartao, webhooks idempotentes. Reusar. Faxina: shadow table morta, slowapi orfa, PK BigInt vs regra UUID. |
| **asaas** | REAL | Pix in/out validado, security-validator, fila idempotente, webhook so-atualiza. Confiar. So mover ~5 os.getenv pra Settings + apagar .md/coverage. |
| **infinitepay** | REAL | Gateway cartao coeso, idempotente, fila persistente, IA via app interno. Dos mais maduros. Faxina: os.getenv + GET /webhook publico vaza status. |
| **promoter** | REAL | Limpo e fiel: 3 camadas, ref-URL + validate-ref + promocao via coordinator. Reusar. Falta notify em .md + suspender/reativar. |
| **candidate** | REAL | Funil 3 camadas bem alinhado. Reusar. Remover etapas EDUCATION/BIRTH inventadas, resolver role candidate-vs-lead, apagar GAPS.md. |
| **training** | REAL | Funil candidate->training->promoter completo, correcao IA assincrona >=6. Reusar. Ajustes: notify ao trainee, limpar metrics.py. |
| **student** | REAL | 11 endpoints, funil 10 status, integracoes reais. Reusar. CORRIGIR inversao de ator no diploma + shadow table morta + dropar wiki. |
| **fees** | REAL | Money-path idempotente, gate coordinator, webhook desmilitarizado. Reusar. CONFIRMAR sentido do dinheiro (payout vs charge) + list vaza entre polos. |
| **ai** | REAL | 4 integracoes reais (DeepSeek/Gemini/ElevenLabs/Vision). Reusar nucleo. Apagar DB-delirio + schemas mortos; faltam endpoints de dominio (correcao/selfie/RG/fraude). |
| **enrollment** | PARCIAL | Logica do funil quase toda pronta MAS o router autenticado NAO sobe no main.py — funil inteiro inacessivel. Bug critico de montagem. |
| **profiles** | PARCIAL | CRUD solido e acima da media. Refatorar: matar FK/shadow auth, 3 camadas, add campo 'escola'. |
| **auth** | PARCIAL | _provision REAL, mas contradiz a propria razao: User sem cpf/phone/email/unique (§10). atomic.py invade 4 apps. Expurgar role_rules/refresh_tokens/LEAD. |
| **hub** | PARCIAL | Nucleo limpo (model/seed/migration). Faxina: 3 camadas, services vazio, apagar CLAUDE.md, gate via roles HTTP. address orfao. |
| **roles** | REAL* | Motor real (regras no .env, assign/promote/acumulo). Cirurgia: shadow table, users.py duplicado, 3 camadas, role_rules orfa. |
| **staff** | PARCIAL | Spine solido. Dominio hubs e delirio: camada errada + proxy sem token. Health so monitora hub. Reescrever parte de hubs. |
| **coordinator** | PARCIAL | So 3 CRUDs locais. Coracao (aprovar->promover, pagar taxas, ciclo prova, diploma, comissao) FALTANDO/STUB. pay_fee finge pagamento. |
| **address** | PARCIAL | ViaCEP+CRUD real. Cirurgia pesada: FK/shadow cross-schema, 3 camadas, escopo inventado EntityAddress, upload em uploads/. |
| **notify** | PARCIAL | Motor de envio multicanal REAL e robusto (melhor pedaco). Mas shadow+FK+PK Integer, sem 3 camadas, Mailcow admin fora de escopo, SQLite solto. |
| **commissions** | STUB | Payout e DELIRIO: paga placeholder da empresa, soma tudo num Pix, bonus errado, sem externalReference/fila, asaas mock. REESCREVER. |
| **documents** | STUB | BUG FATAL: service escrito em Tortoise ORM sobre models SQLAlchemy — NENHUMA rota roda. Reescrever service. Manter models/migration/schemas. |
| **jwt** | PARCIAL | Nucleo RS256+JWKS real e bom. Amputar DB-delirio inteiro (shadow table, alembic vazio, deps SQLAlchemy/slowapi). |
| **otp** | DESCOMISSIONAR | Dono mandou "so conectar no postgres"; IA fez microsservico inteiro nao-pedido + shadow+FK+SQLite solto. Candidato a DELETE, nao reescrita. |

Resumo: **9 REAL** (lead, asaas, infinitepay, promoter, candidate, training, student, fees, ai; roles quase) · **8 PARCIAL** (enrollment, profiles, auth, hub, staff, coordinator, address, notify, jwt) · **2 STUB** (commissions, documents) · **1 DESCOMISSIONAR** (otp). Nenhum VAZIO.

---

## 2. MONEY-PATH (o caminho do dinheiro)

Ordem do fluxo: **lead paga -> asaas/infinitepay cobram -> fees (taxa matricula) -> commissions paga promotor/coordenador**. Enrollment e promoter sao o handoff.

### Pronto e confiavel (NAO reescrever)
- **asaas** — entrada (charge PIX) e saida (payout pixkey/qrcode) REAIS e validados. Intencao commitada antes do submit, `Idempotency-Key=payment_id`, webhook so atualiza (retorna None se nao acha, nunca cria). Fila persistente `outbound_jobs` com backoff. security-validator aprova so saidas que o app iniciou. Fuso America/Sao_Paulo explicito. Memoria confirma paridade prod/dev 27/05.
- **infinitepay** — gateway cartao paralelo. `order_nsu=external_id` como chave de idempotencia, webhook NUNCA cria Checkout (404 se desconhecido), confirmacao out-of-band via payment_check antes de marcar pago. Fila `outbound_queue` com claim atomico. Migration 0002 ja dropou a FK cross-schema (o unico app que limpou isso).
- **lead** — funil de pagamento completo: PIX sincrono + cartao async, webhooks asaas-charge/infinitepay idempotentes que so atualizam. NAO emite cobranca propria (chama os apps internos — fronteira §6 correta).
- **fees** — money-path idempotente: intencao commitada, `payment_id` deterministico `fee-{id}-{kind}`, webhook desmilitarizado so-atualiza. Status da taxa DERIVADO dos 2 pagamentos. fees NAO libera acesso, so guarda status (§6 respeitado).

### Delirio (NAO confiar — reescrever)
- **commissions — o pior do money-path.** Confirma o diagnostico ja na MEMORY:
  - paga `pix_key='company_pix_key_placeholder'` (paga a EMPRESA, nao o beneficiario) — `payment_batch_service.py:117` e `commissions.py:288`.
  - soma TODAS as comissoes num unico Pix em vez de 1 pagamento por pessoa — `payment_batch_service.py:116-120`.
  - bonus em DUAS versoes erradas: uma escala `promoter_count*50c` (`commissions.py:226-228`, dono proibiu escalar), outra da bonus global se leads>=10 (`payment_batch_service.py:164-170`).
  - SEM `externalReference` de idempotencia no payout (`asaas_client.py:57` nem aceita o param) — viola §12.
  - SEM fila persistente / sem tratamento de saldo insuficiente; `get_payout_status` e codigo morto.
  - asaas MOCKADO em dev/test (`asaas_client.py:77-84`) — mascara que o payout nunca foi exercido (dev usa Asaas REAL).
  - valores em config errados por fator 100: promoter=100 centavos (R$1) vs R$100 esperado; bonus_threshold=10 vs >=5.
- **fees — possivel inversao de sentido (CONFIRMAR com dono).** Modela a taxa de matricula como PAYOUT/Pix-OUT (`pay_qrcode`/`pay_qrcode_scheduled` = pagar BR Code de terceiro). Taxa cobrada deveria ser charge/Pix-IN (dinheiro entrando). Nao e bug de codigo — e interpretacao do desenho. `fee_payment.py:3-4`, `asaas.py:27,49`.
- **coordinator — pay_fee finge pagamento.** `pay_enrollment_fee` seta status='paid' e copia `payment_external_id` que VEM DO REQUEST BODY. Nao chama asaas, sem QR, sem ID deterministico, sem webhook. `services/__init__.py:206-220`. Viola §7 e §12.

### Faltando no money-path
- **commissions**: gatilho real de "lead pagou -> comissao" nunca e conectado; coordenador do hub nunca e resolvido; sem webhook que atualize status do payout (PAID nunca e atingido pelo fluxo).
- **fees**: reconciliacao ausente — `get_payment` existe mas nunca e chamado; PENDING fica eterno se o webhook se perder (mesma classe de bug ja vista no asaas).
- **enrollment/lead handoff**: `notify_enrollment` / `notify_promoter_completed` so disparam se `WEBHOOK_*_URL` estiverem setadas; default vazio => hoje inerte (isso e config, nao delirio; memoria diz que /webhook/new ja foi corrigido em dev).
- **lead -> enrollment vinculo ao hub**: `Enrollment.hub_external_id` NUNCA e preenchido (so promoter_external_id) — depende do hub service; coordenador acaba nao sendo notificado de verdade.

---

## 3. DELIRIOS E VIOLACOES DE CONVENTION (agrupados, com app:arquivo:linha)

### 3.1 — Shadow table `auth.users` + FK cross-schema (§4/§6) — A VIOLACAO MAIS SISTEMICA
Quase todo app declara uma `Table('users', schema='auth')` "pra o SQLAlchemy resolver FK cross-schema" — exatamente o que §4 proibe nominalmente. Em vários e codigo MORTO (nenhum model usa).

- **address** — `db.py:33-39` shadow + `models/address.py:24-31` FK REAL + materializada em ambas migrations (0001:65-71, 0002:87-93). **A FK e usada** (deteccao por substring em `address_service.py:31-40`).
- **profiles** — `db.py:33-39` shadow + `models/profile.py:31-36` FK + migration 0001:57-63. Service depende da FK (`profile_service.py:97-100`).
- **notify** — `db.py:36-42` shadow + FK em `contact.py:24-29` e `log.py:29-34` + migration 0001:52-58. **FK fisica real no banco.**
- **commissions** — `db.py:33-39` shadow + `commission.py:27-38` FK + migration create_commissions:94-98.
- **otp** — `db.py:36-42` shadow + FK nos 3 models (otp.py:21, pending_notify.py:21, rate_limit.py:18) + migration 0001:45-51,79-85. **FK fisica real.**
- **MORTAS** (shadow declarada, nenhum model usa, e ainda mente em comentario/docstring): **ai** `db.py:33-39` (app stateless, asyncpg nem nas deps); **auth** schema tem `role_rules`+`refresh_tokens` orfas; **coordinator** `db.py:33-39` (+ PRD inverte §4 citando-a como compliance); **enrollment** `db.py:33-39` (FK real e intra-schema); **jwt** `db.py:33-39` (app "zero banco"); **lead** `db.py:39-44` (migration 0001 sem FK); **roles** `db.py:34-40` (contradiz o proprio model); **student** `db.py:40-45` (+ docstring da migration mente "FK cross-schema").

> Unico que LIMPOU: **infinitepay** (migration 0002 dropa as FKs). Mas o downgrade as RECRIA (`drop_auth_users_fks.py:46-79`).

### 3.2 — Ausencia das 3 camadas de API public/authenticated/demilitarized (§3/§5) — QUASE UNIVERSAL
LEI de arquitetura do dono. So um punhado segue de verdade.

- **Seguem corretamente**: lead, candidate, promoter, infinitepay (+ fees, training com pequenos desvios).
- **Violam (api/ flat, sem gates)**: **address**, **ai** (+ rotas duplicadas canonico/legado em `router.py:28-36`), **auth** (`router.py:5-21` — publicos/autenticados/admin todos soltos), **coordinator**, **documents**, **hub** (router interno nomeado 'public' em `hubs.py:19` quando devia ser demilitarized), **jwt**, **notify** (so demilitarized/ — admin Mailcow perigoso sem auth), **otp**, **profiles**, **roles**, **commissions** (so demilitarized/ + DUAS familias de rota duplicadas), **staff** (so authenticated/, dominio na camada errada), **enrollment** (so authenticated/ + webhooks soltos), **student** (so authenticated/).

### 3.3 — Mock / placeholder no caminho do dinheiro
- **commissions** `payment_batch_service.py:117` + `commissions.py:288` — `pix_key='company_pix_key_placeholder'`.
- **commissions** `asaas_client.py:77-84,124-125` — PayoutResult mock fixo (`mock_transfer_id`) em dev/test.
- **coordinator** `services/__init__.py:206-220` — pay_fee marca 'paid' com payment_external_id do request body, sem asaas.
- **staff** `integrations/hub.py:46-48` — proxy repassa create_hub/set_coordinator ao hub SEM JWT (valida o token e descarta).

### 3.4 — BUGS FATAIS / codigo que nunca rodou
- **documents** — `services/document_service.py` inteiro usa API do **Tortoise ORM** (`.get_or_none().prefetch_related()`, `.create()`, `.save()`) sobre models **SQLAlchemy 2.0**. Esses metodos NAO existem; toda rota estoura AttributeError. App e casca. Nunca usa `get_session()`.
- **enrollment** — `main.py:81-83` monta so webhooks+enrollments+health e IGNORA `app/api/router.py` que agrega as 6 rotas autenticadas. `api_router` nao e importado por ninguem. **O funil de matricula inteiro NAO sobe** (so webhook+audit+health respondem).

### 3.5 — PK BigInteger/Integer em vez de UUID (§4)
- **lead** (lead.py:25, checkout.py:17, message.py:19) — ironicamente o "app-modelo de referencia".
- **notify** (Contact/Message/Log/Template Integer autoincrement).
- **commissions** (Commission/PaymentBatch BigInteger).

### 3.6 — Escopo inventado pela IA (nao pedido pelo dono)
- **address** — feature `EntityAddress` polimorfica (proof upload, unlink, `external_id` String(100) livre), webhook generico hardcoded `http://10.10.10.129`, upload em `uploads/` (proibido §17). Comentarios se autodenominam "feature do LOCAL".
- **candidate** — etapas EDUCATION + BIRTH (sao do funil ENROLLMENT, nao do candidate); `GAPS.md` recomenda adicionar pagamento ao candidate (candidato NAO paga). Contradiz a regua.
- **otp** — microsservico completo (fila retry, rate-limit duplo, prometheus, webhook, /status rico) quando o dono pediu so "conecte com postgres".
- **notify** — `integrations/mailcow.py` (484 linhas, CRUD admin de servidor de email) + `whatsapp.py` com 18 metodos (a maioria mortos). Fora do escopo "disparar notificacao".
- **coordinator** — PRD de 17KB descreve ExamCycle/10-estados/8-endpoints/orquestracao que NADA existe no codigo (so 3 CRUDs).

### 3.7 — os.getenv espalhado em vez de pydantic-settings (§2)
- **asaas** `webhook_security.py:43,73,100,118,140` + `config_status.py:34` (+ default sentinela em-dash fragil).
- **infinitepay** `webhook_security.py:73,76,111,125,151,178,209` + `main.py:52,55`.

### 3.8 — Docs/PRDs/wiki antes do FIM + header "SUPERSEDED" enfiado pela IA (LEI do dono + §19)
Header `SUPERSEDED — ver .claude/prds/<app>.prd.md` no topo do TODO do dono (a VISAO manda ignorar): **coordinator**, **documents**, **enrollment**, **hub**, **promoter**, **roles**, **staff**.
Wiki proibida ainda presente: **enrollment** (`wiki/enrollment.md`), **student** (`wiki/student.md`).
Docs sobrando: **asaas** (API.md, INTEGRATION.md, MIGRACAO_F3.md), **documents** (2 PRDs contraditorios), **hub** (CLAUDE.md descrevendo testes inexistentes).

### 3.9 — Ruido proibido versionado (§17)
`.coverage`/`coverage.json`: asaas, commissions, profiles, staff. SQLite solto (`.db-wal`/`.db-shm`): notify, otp. `.venv/` versionada: documents. `requirements-dev.txt` coexistindo com pyproject: asaas. Artefato `commissions/=24.1` (log de build do uv). `.mcp.json` por-app com chave hardcoded: ai.

### 3.10 — Libs fora da stack canonica sem justificativa (§2)
`prometheus-client` + `slowapi` aparecem em quase todo app sem registro (a CONVENTION exige justificar). Casos com dep nao-declarada mascarada por try/except ImportError: profiles, documents, training. `fastapi-structured-logging` em auth e staff. slowapi declarada mas NUNCA usada: lead (dep orfa), jwt.

---

## 4. REUSAR vs REESCREVER

### REUSAR (pronto/solido — no maximo faxina cirurgica)
| app | o que aproveitar |
|---|---|
| asaas | TUDO. App interno Pix in/out validado. So mover os.getenv + apagar ruido. |
| infinitepay | TUDO. Gateway cartao maduro. So os.getenv + avaliar GET /webhook publico. |
| lead | TUDO o nucleo (funil, integracoes via app interno, webhooks). Faxina shadow/PK/slowapi. |
| promoter | TUDO. Mais limpo do conjunto. So acabamento (notify .md, suspender). |
| training | TUDO o funil. Limpar metrics.py + comentario falso. |
| candidate | Nucleo do funil. Remover etapas inventadas + GAPS.md. |
| student | App inteiro. Corrigir inversao diploma + apagar shadow morta + wiki. |
| ai | 4 integracoes (DeepSeek/Gemini/ElevenLabs/Vision). Apagar DB/schemas mortos. |
| profiles | CRUD Profile/BirthInfo/Educational (qualidade acima da media). Refatorar fronteira. |
| roles | Motor (rule_catalog .env + assign/promote/acumulo). Cirurgia em volta. |
| jwt | Nucleo RS256+JWKS. Amputar DB-delirio. |
| hub | model/db/migration/seed/schemas (dos mais limpos). Faxina estrutura. |
| fees | Espinha do money-path idempotente. Confirmar sentido + escopar por hub. |
| enrollment | Logica de negocio quase inteira (services/models/maquina de estados). MONTAR o router. |
| auth | register/_provision + 7 clients de integration + auth_guard. |
| notify | Motor de envio multicanal (message_service + integrations). Melhor pedaco do repo. |
| documents | models + _mixins + migracao + schemas + pii.py (SQLAlchemy, bons). |
| staff | Spine (config/db/dependencies JWT/health). |
| coordinator | So os 3 models + esqueleto de CRUD. |

### REESCREVER (delirio / nao confiar no fluxo)
| app | o que reescrever |
|---|---|
| **commissions** | Nucleo de payout INTEIRO (placeholder, soma tudo, bonus, sem externalReference/fila, mock). Aproveitar so models (UUID+sem FK), timing do worker e schemas. Eliminar duplicacao service/service e router/router. |
| **documents** | `document_service.py` inteiro (Tortoise sobre SQLAlchemy — nao roda). Reescrever em SQLAlchemy async + provisionamento eager. |
| **coordinator** | Toda a logica de negocio (aprovar->promover via roles, pagar via asaas, ciclo prova, diploma, comissao, notify) + estrutura api/. Preservar so models. |
| **staff** (parcial) | Parte de hubs (camada errada + proxy sem token) e health-aggregate (so monitora hub). Spine fica. |
| **otp** | Decisao do dono: DELETE (candidato a descomissionar). Se manter: arrancar FK/shadow, cortar nao-pedido. |

---

## 5. LACUNAS (FALTANDO) POR FUNIL

### Funil do ALUNO: lead -> enrollment -> student
- **lead -> enrollment**: handoff inerte ate `WEBHOOK_ENROLLMENT_URL` ser configurado (config, nao codigo); rota destino real `/webhook/new`.
- **enrollment NAO SOBE**: bug critico de montagem (3.4) — o funil de matricula inteiro esta inacessivel via HTTP no app real. Maior lacuna funcional do funil do aluno.
- **enrollment hub**: `hub_external_id` nunca preenchido -> coordenador nao e notificado de verdade. Depende do **hub service** que nao expoe endpoint de vinculo.
- **enrollment "aguardando liberacao"**: a etapa de o coordenador inserir dados de acesso e promover existe no codigo (`release.py`) mas nao sobe (mesmo bug).
- **student inversao de ator**: dono quer o COORDENADOR postando a foto do aluno com diploma -> veteran; o codigo poe o ALUNO (`diplomas.py:44-48`).
- **student validacao IA raso**: aprova qualquer descricao nao-vazia, nunca reprova (`document_service.py:172-179`).
- **fees sentido do dinheiro**: a confirmar (payout vs charge) + vazamento de taxas entre polos + reconciliacao ausente.
- **selfie real**: pedida como "validacao tipo assinatura" no candidate E enrollment — em ambos e so heuristica de busca de palavras na descricao do ai/vision, nao liveness/biometria.

### Funil do PROMOTOR: candidate -> training -> promoter -> coordinator
- **candidate -> training**: handoff incompleto — promove o papel no roles mas NAO cria o registro no app training (`selfie.py:11-13`). Metade do handoff falta.
- **candidate etapas erradas**: EDUCATION/BIRTH inventadas (sao do funil do aluno).
- **training -> promoter**: COMPLETO e correto (aprovacao do coordenador promove via roles, bloqueante).
- **training curriculo**: nao ha curso/modulo/ordem — todas as materias do banco formam um trilho global unico (ok pra MVP, nao escala).
- **coordinator e o elo mais fraco**: quase tudo do papel FALTA — nao aprova training->promoter via roles (so UPDATE local), nao insere dados de acesso, pay_fee finge pagamento, ciclo de prova migrou pro student, diploma/veteran nao acontece nele, comissao do coordenador nunca dispara (`coordinator_commission_cents` morto).
- **promoter status**: SUSPENDED existe e barra captacao/comissao, mas NAO ha endpoint para suspender/reativar — status nunca muda de ACTIVE.
- **promoter notify**: so 1 evento (created); suspensao/reativacao nao notificam; mensagens hardcoded no .py em vez de notify/messages/*.md.

### Transversal (ambos os funis)
- **notify**: sem rota inbound de webhook do Evolution/WhatsApp -> status de entrega WhatsApp e OTIMISTA (marca SENT no 201, sem confirmacao). Memoria cita `/api/v1/webhook/notify` como rota real — nao existe neste codigo.
- **auth NAO e fonte de verdade**: User sem cpf/phone/email nem unique constraint (§10 violada) — unicidade terceirizada; CPF sem digito verificador.
- **IA (§14) nao plugada onde a regua sugere**: fraude/recibo em asaas/lead; flag CPF suspeito em auth; anomalia de volume em commissions; extracao RG/CNH em documents. Degradavel, nao bloqueia.
- **provisionamento eager**: documents deveria criar TODOS os sub-docs no cadastro (hoje lazy); address nao consegue criar "endereco vazio" (campos NOT NULL).
