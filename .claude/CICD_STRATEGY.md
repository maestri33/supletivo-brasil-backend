# Estratégia de CI/CD — Backend Supletivo

> **Status:** PLANO para você aprovar. **Nada foi implementado.** Não vou escrever
> nenhum workflow, script ou mudança de código sem o seu OK explícito.
> **Data:** 2026-05-28 · **Autor:** Claude (sessão de estratégia) · **Idioma:** pt-br.
>
> Este documento é o diagnóstico + proposta. Onde eu afirmo algo, eu **verifiquei no
> repositório** (li o `ci.yml`, o `docker-compose.prod.yml`, os `scripts/`, o
> `RUNBOOK.md`, os testes dos 5 serviços de dinheiro, o teste e2e, o `.gitignore` e
> consultei o GitHub: branch padrão, proteção de branch e histórico de execuções).

---

## 0. TL;DR — o essencial em 1 minuto

A boa notícia: **já existe um CI de verdade** (lint + testes + cobertura + e2e), os
segredos **não estão vazados** no código, e cada serviço tem seu próprio `uv.lock`
(isso facilita muito tudo daqui pra frente). Você não está começando do zero.

A má notícia: **esse CI hoje não protege nada**, por 3 motivos somados:

1. **Ele não roda no lugar certo.** O CI dispara em `branches: [main]`, mas o seu
   branch padrão é `master` e **não existe `main`**. Resultado: no branch que importa,
   o CI **nunca rodou** (só o robô de dependências do GitHub rodou lá).
2. **Não tem cadeado.** O `master` **não tem branch protection**. Mesmo que o CI
   rodasse e ficasse vermelho, **nada impede um merge** ou um push direto. O "portão"
   (`ci-gate`) existe no papel mas não está plugado em nada.
3. **Ele está vermelho** — e CI vermelho que ninguém é obrigado a respeitar vira
   ruído que todo mundo ignora.

E o achado mais sério, ligado direto à sua regra inegociável nº 2:

> 🚨 **O teste `tests/e2e/money_path` é uma arma carregada apontada pra produção.**
> Ele sobe o `lead` **real**, sem nenhum mock, e o `lead` real chama Asaas e
> InfinitePay **reais**. Hoje o único motivo de ele não gerar uma cobrança PIX
> verdadeira é que o teste esbarra num erro de autenticação e **desiste** (`skip`).
> Se alguém "consertar" esse env apontando pros endpoints certos, o teste passa a
> **criar cobrança real no seu gateway de produção**. Isso viola a sua regra nº 2.
> _(Os testes unitários dos 5 serviços de dinheiro, esses sim, estão bem isolados —
> não tem esse risco. O problema é só o e2e.)_

**Se você só fizer 1 coisa esta semana → [Seção 5](#5-se-você-só-puder-fazer-uma-coisa-esta-semana).**

---

## 1. Como ler este documento

- **Seção 2** = o que está acontecendo hoje (o diagnóstico honesto).
- **Seção 3** = o plano em fases, do mais barato/seguro pro mais sofisticado.
- **Seção 4** = as decisões que **só você** pode tomar (eu não decido sozinho).
- **Seção 5** = a única coisa que vale a pena fazer já.

Sempre que eu recomendar algo, tem um **_Por quê:_** em linguagem simples.

---

## 2. Diagnóstico — o estado atual (verificado, sem achismo)

### 2.1 O que JÁ existe e está bom ✅

| Item | Situação |
|---|---|
| **CI com estrutura real** | `lint` (ruff) + `test` (pytest) + `coverage` (gate 60/40) + `e2e` + `ci-gate`, tudo em matriz por serviço. |
| **Cache de `uv`** | Já ligado (`astral-sh/setup-uv@v5` com `enable-cache: true`). Não precisa fazer nada aqui. |
| **Segredos NÃO vazados** | `.gitignore` cobre `.env` e `.env.*` (só libera `.env.example`). Nenhum `.env` real está versionado. Varredura por chaves (`aact_`, `sk-`, PEM, `gho_`) → **10 ocorrências, todas falso-positivo** (validação de prefixo, exemplos, docstrings). |
| **Testes unitários isolados do dinheiro real** | asaas, infinitepay, lead, fees, commissions: nenhum teste unitário bate em Asaas/InfinitePay reais. Usam mock/monkeypatch/respx + SQLite em memória + app em processo (ASGI). |
| **`uv.lock` por serviço** | Cada serviço é independente → dá pra rodar/cachear/deployar **só o que mudou**, e o build é reprodutível. |
| **Infra de produção madura** | O `docker-compose.prod.yml` já tem Traefik (proxy+TLS), Prometheus/Loki/Grafana (observabilidade) e até Infisical (gerenciador de segredos) — base boa pra construir. |

### 2.2 O que está QUEBRADO agora 🔴

| # | Problema | Por que importa | Gravidade |
|---|---|---|---|
| **B1** | CI dispara em `main`, mas o branch padrão é `master` (não existe `main`). | O CI **não roda** onde o trabalho acontece. Proteção zero. | 🔴 Crítico |
| **B2** | `master` **sem branch protection**. | Dá pra dar merge/push com CI vermelho ou sem CI. O portão é decorativo. | 🔴 Crítico |
| **B3** | `tests/e2e/money_path` sobe o `lead` real → chama Asaas/InfinitePay reais. Só não cobra hoje porque falha no auth e dá `skip`. | **Viola a regra nº 2.** Um "conserto" ingênuo do env vira cobrança real em produção. | 🔴 Crítico |
| **B4** | É o e2e também que **deixa o CI vermelho**: o `lead` não sobe porque o job não passa as variáveis obrigatórias (`INFINITEPAY_BASE_URL`, `AUTH_BASE_URL`, `JWT_BASE_URL`, `NOTIFY_BASE_URL`, `PROFILES_BASE_URL`, `PROMOTER_DEFAULT`) e não há `lead/.env`. | CI sempre vermelho = CI ignorado. | 🔴 Crítico |
| **B5** | O "caminho do dinheiro" do CI **≠ o seu**. O gate de cobertura 60% cobre `lead asaas infinitepay enrollment candidate training`, mas o seu money path é `lead asaas infinitepay fees commissions`. **`fees` e `commissions` estão só no nível 40%.** | Dois serviços de dinheiro seus têm gate **mais fraco** do que deveriam. | 🔴 Crítico |
| **B6** | Matriz feita à mão e desalinhada: `documents` está no `lint` e `coverage` mas **fora do `test`**; `ai` está fora do `coverage`; o `asaas/tests_pg/` (provas de idempotência no Postgres real) **não roda no CI** (`testpaths = ["tests"]`). | Buracos silenciosos de cobertura no money path (idempotência de payout não é verificada no CI). | 🟠 Alto |
| **B7** | Execuções recentes aparecem como "failure" em 0s — em parte por `concurrency: cancel-in-progress` cancelando pushes em sequência. | Confunde o sinal: parece que quebrou, mas às vezes só foi cancelado. | 🟡 Médio |

### 2.3 Sobre a regra nº 2 (CI nunca pode bater em Asaas/InfinitePay/CPFHub reais)

**Veredito:** os **testes unitários estão seguros** — verifiquei serviço por serviço:

- **asaas** → nenhum teste sai pra internet. O cliente HTTP (`AsaasClient`) é substituído
  por um mock (`fake_asaas`). _Mas há um furo de defesa:_ a URL base padrão é
  `https://api.asaas.com` (produção) e o conftest **não** a sobrescreve. A segurança
  depende 100% de o autor lembrar de usar o mock. Um teste futuro distraído poderia
  disparar pra produção (com chave fake → tomaria 401, mas é uma chamada real).
- **infinitepay** → seguro (mock + `respx`). CPFHub nem existe aqui (é do asaas/auth).
- **lead / fees / commissions** → seguros (mock + SQLite + app em processo). _Furo
  parecido:_ `commissions` só fica offline porque `env` cai no default `"dev"`; se o
  CI definisse `ENV=prod`, o caminho de payout tentaria uma chamada real.
- **e2e money_path** → **NÃO é seguro** (problema B3 acima).

**Conclusão:** a regra nº 2 está *quase* respeitada, mas apoiada em disciplina humana,
não em barreira técnica. A correção certa é **defesa em profundidade**: um "muro" que
faz qualquer teste **falhar na hora** se tentar abrir um socket pra fora (detalhe na
Fase 1). Assim a segurança não depende de ninguém lembrar de nada.

### 2.4 Achados urgentes que NÃO são de CI/CD (mas você precisa saber)

Apareceram durante a investigação. Não são o foco deste plano, mas são sérios:

1. 🚨 **InfinitePay sem verificação de webhook.** O arquivo `webhook_security.py` foi
   **apagado** (−226 linhas) e o endpoint de webhook **não valida mais assinatura HMAC
   nem IP de origem**. Os testes ainda esperam que valide (vão falhar). Isso está no
   branch atual (`fix/lead-review-2026-05-28`), então provavelmente é trabalho **em
   andamento** — mas **antes de qualquer deploy**, a verificação do webhook de
   pagamento precisa voltar. **Me confirma se a remoção foi intencional?**
2. ⚠️ **Backups podem estar vazios.** O cron de backup aponta pra `localhost:5433`
   (porta de **dev**), e vários arquivos em `backups/` têm 123–161 bytes (ou seja,
   provavelmente só capturaram mensagem de erro). **Você não tem garantia de que tem
   um backup restaurável.** Isso é grave e independe de CI/CD.
3. ⚠️ **Infisical não está plugado.** Ele existe no compose mas atrás de um
   `profile` (nem sobe no `up` normal) e **não alimenta nenhum app**. Hoje os segredos
   vêm todos de **um único `.env`** na raiz. É um plano futuro, não uma realidade.
4. ⚠️ **Caddy vs Traefik — quem manda no 443?** A produção que está rodando hoje usa
   um **Caddy numa LXC separada** terminando TLS. O `docker-compose.prod.yml` deste
   repo usa **Traefik interno** terminando TLS no mesmo 443. **Os dois não podem
   disputar a porta 443.** Decisão de topologia a resolver antes de automatizar deploy.

---

## 3. Proposta — em fases (barato e seguro primeiro)

Princípio: **cada fase deixa o sistema mais seguro sem quebrar o que funciona, e cada
uma entrega valor sozinha.** Você pode parar em qualquer fase.

### Fase 0 — Fazer o CI funcionar e travar de verdade · esforço: **S** · 🟢 começa aqui

**Objetivo:** transformar o CI que já existe num portão **verde** e **obrigatório**,
sem tocar em código de aplicação.

| Passo | O quê | Por quê |
|---|---|---|
| 0.1 | Trocar o gatilho do CI de `main` → `master` (e também rodar em PRs pra `master`). | Sem isso, o CI não roda onde você trabalha. É **uma linha**. |
| 0.2 | **Tirar a bomba:** desligar (ou neutralizar) o job `e2e-smoke money_path`. | Ele (a) reda o CI e (b) pode gerar cobrança real. E hoje ele nem testa o dinheiro de verdade (desiste no `skip`). Melhor desligar do que fingir que protege. |
| 0.3 | Corrigir o money path do gate de cobertura: nível 60% = **`lead asaas infinitepay fees commissions`** (o **seu** money path). | `fees` e `commissions` são dinheiro e hoje estão no gate fraco (40%). |
| 0.4 | Ligar **branch protection** no `master`: exige `ci-gate` verde + PR pra dar merge. | É o **cadeado**. Sem ele, todo o resto é teatro. |
| 0.5 | Acertar a matriz: incluir `documents` no `test`, decidir `ai` no `coverage`. | Tapar buracos silenciosos. |

**Resultado:** depois da Fase 0, **nenhuma mudança entra no `master` sem lint+testes
verdes**, e nada no CI encosta em pagamento real. Tudo isso **sem mexer em app**.

> _Nota:_ o e2e money path **bem feito** (com Asaas/InfinitePay **falsos**) é valioso e
> volta na Fase 1. Na Fase 0 a gente só remove o perigo imediato.

### Fase 1 — CI inteligente + blindagem do dinheiro · esforço: **M**

| Passo | O quê | Por quê |
|---|---|---|
| 1.1 | **Rodar só o que mudou.** Detectar serviços afetados pelo diff (ex.: `dorny/paths-filter`) e montar a matriz dinamicamente. | Hoje roda os 22 sempre. Mudou só o `lead`? Roda só o `lead`. Mais rápido e mais barato. |
| 1.2 | **Muro anti-internet nos testes** (defesa em profundidade): um fixture global que **bloqueia qualquer conexão de saída** durante os testes (libera só `localhost`/Postgres do CI). | Fecha de vez a regra nº 2: nenhum teste consegue tocar Asaas/InfinitePay real, **mesmo que o autor esqueça o mock**. |
| 1.3 | **Marcar os testes de regressão do dinheiro** (ex.: `-m moneypath`) e exigir que **eles** passem no gate — não só "cobertura ≥ X%". | Cobertura é proxy fraco. O que importa é: idempotência, webhook aplica certo, ID determinístico. Esses testes já existem; só falta marcá-los e exigi-los. |
| 1.4 | Reescrever o e2e money path com Asaas/InfinitePay **stub** (serviços falsos locais) e ligá-lo de volta. | Aí sim um e2e que testa o fluxo de ponta a ponta **sem risco** e sem `skip` mascarando falha. |
| 1.5 | Rodar `asaas/tests_pg/` no CI (com Postgres) — são as provas de não-duplicação de payout. | Idempotência de dinheiro é o que mais dói se quebrar. |

### Fase 2 — Segurança · esforço: **M**

| Passo | O quê | Por quê |
|---|---|---|
| 2.1 | **Secret-scanning** (gitleaks) no CI **e** como pre-commit. Falha o build se achar credencial. | Sua regra nº 3. Hoje você depende só da disciplina do `.gitignore`, e tem um `.env` real de 15 KB do lado (um `git add -f` de distância do desastre). |
| 2.2 | **Audit de dependências** (`uv`/`pip-audit`) — alerta sobre libs com CVE. | Saber quando uma dependência ficou vulnerável. Começa como **aviso**, não bloqueio. |
| 2.3 | **Gate do dinheiro** formal: o `ci-gate` exige explicitamente os testes `moneypath` (Fase 1.3) verdes. Plugado no branch protection. | É a materialização da sua regra nº 1: **dinheiro quebrado = merge bloqueado.** |
| 2.4 | Allowlist no scanner pros falso-positivos conhecidos (prefixo `$aact_prod_*`, docstrings PEM). | Pro scanner não "gritar lobo" e você parar de confiar nele. |

### Fase 3 — CD (deploy seguro pra produção) · esforço: **L**

Aqui mora a decisão de arquitetura ([Seção 4](#4-decisões-que-só-você-pode-tomar)).
O `docker-compose.prod.yml` **puxa imagens** (`image: supletivo/<svc>:${TAG:-latest}`),
**não constrói** — então o desenho natural é:

```
   GitHub Actions (na nuvem, SEM acesso à sua produção)
   ├─ build da imagem do serviço que mudou
   ├─ scan da imagem (trivy/grype)
   ├─ tag IMUTÁVEL = hash do commit (nada de :latest em prod)
   └─ push pro registry (GHCR — privado, grátis, junto do repo)
                    │
                    ▼   ⟵ APROVAÇÃO MANUAL (você) acontece aqui
   Na LXC de produção (10.1.30.20):
   └─ você roda  ./deploy.sh <tag>
      ├─ 1. backup do Postgres ANTES de tudo
      ├─ 2. docker compose pull (baixa a imagem nova por tag)
      ├─ 3. alembic upgrade head (migrations, com cuidado)
      ├─ 4. up -d --force-recreate <serviço>   (nunca "restart": não relê .env)
      └─ 5. smoke test contra api.supletivo.net (Traefik) → deu certo?
```

| Passo | O quê | Por quê |
|---|---|---|
| 3.1 | CI **builda + escaneia + empurra** imagem por **tag = commit SHA** pro GHCR. | Tag imutável é o que **torna rollback possível**: "volta pra imagem de ontem" = redeploy do SHA anterior. Hoje tudo é `:latest` e a imagem antiga some. |
| 3.2 | **Aprovação manual** antes de prod (GitHub *Environments* com required reviewer = você, ou simplesmente você rodando o `deploy.sh` à mão). | Você no controle. Nada vai pra produção sozinho. |
| 3.3 | `deploy.sh` de **um comando**: backup → pull → migrate → recreate → smoke. | O operador (você) não precisa decorar 5 comandos nem lembrar do "force-recreate". |
| 3.4 | `rollback.sh` de **um comando**: volta pro SHA anterior + (se preciso) restaura backup. | Reverter em 1 passo, sem precisar saber git/docker/psql na pressão. |
| 3.5 | **Migrations com rede de segurança**: backup obrigatório antes; preferir "corrigir pra frente" a `downgrade`; revisar o SQL antes de aplicar. | `alembic downgrade` em produção é arriscado. Backup + forward-fix é mais seguro. |

**Runner self-hosted na LXC vs registry+pull manual** → decisão em [4.1](#41-como-o-deploy-chega-na-produção).

### Fase 4 — Operação para não-programador · esforço: **S→M**

| Passo | O quê | Por quê |
|---|---|---|
| 4.1 | **RUNBOOK em linguagem de gente**: "pra deployar, rode isto; deu certo se vir aquilo; deu errado, rode o rollback". | Hoje o RUNBOOK pressupõe um dev com SSH+git+docker+psql. |
| 4.2 | **Smoke test que funciona em produção** (bate em `api.supletivo.net` via Traefik). | O atual é amarrado ao dev (`localhost:8001-8022`) — na prod ele dá **tudo-FALHA** e te assusta à toa. |
| 4.3 | **Verificação de backup**: alerta se o dump da noite veio pequeno demais; corrigir a porta do cron (5433→5432). | Pra você **saber** que tem backup bom, não torcer. |
| 4.4 | (Opcional) Um "botão" de deploy/rollback — um comando único, ou um disparo manual no GitHub. | Ergonomia pra solo founder. |

---

## 4. Decisões que só você pode tomar

Não vou decidir essas sozinho — mudam o desenho da implementação.

### 4.1 Como o deploy chega na produção?

| Opção | Como funciona | Prós | Contras |
|---|---|---|---|
| **A) Registry + `deploy.sh` manual** (minha recomendação pra começar) | CI builda/escaneia/empurra imagem; **você** roda `deploy.sh <tag>` na LXC. | Credenciais de prod **nunca** tocam o GitHub. Aprovação manual é natural. Simples. | Você (ou um cron) precisa rodar 1 comando na LXC. |
| **B) Runner self-hosted na LXC** | Um agente do GitHub Actions roda **dentro** da LXC e deploya sozinho. | Deploy "um clique" pelo GitHub. | A LXC de produção fica exposta ao GitHub (mais superfície de risco). Mais peças pra manter. |

_Por quê A:_ sua prod está numa LAN privada (VPN). Mais simples e seguro manter o
GitHub **fora** da prod e você dando o "vai" com um comando. Dá pra evoluir pra B depois.

### 4.2 Quem termina o TLS na porta 443 — Caddy (LXC) ou Traefik (interno)?

A prod rodando hoje usa **Caddy numa LXC separada**. O compose deste repo usa **Traefik
interno**. **Os dois não podem mandar no 443 ao mesmo tempo.** Preciso saber qual é a
verdade pra produção antes de mexer em deploy. (Não precisa decidir agora — só sinalizo.)

### 4.3 Quão rígido fica o cadeado (branch protection)?

- **Mínimo:** PR obrigatório + `ci-gate` verde pra dar merge. (recomendo este pra começar)
- **Rígido:** o acima + proibir push direto + exigir branch atualizado + 1 review.

Como você é solo, "exigir review de outra pessoa" pode te travar. Sugiro o **mínimo**.

### 4.4 Migrations: aplicar no deploy automaticamente ou em passo separado?

Recomendo **dentro do `deploy.sh`, mas depois do backup e com o SQL visível antes de
aplicar**. Em serviço de dinheiro, prefiro você **ver** o que vai mudar no banco.

---

## 5. Se você só puder fazer UMA coisa esta semana

> ### 👉 Fazer a **Fase 0**: deixar o CI verde e obrigatório no `master`, e **tirar a bomba do e2e**.
>
> Em uma frase: **ligue o cadeado e desarme o detonador.**
>
> Concretamente (tudo sem tocar em código de aplicação):
> 1. Apontar o CI pro `master` (1 linha).
> 2. Desligar o job `e2e-smoke money_path` (o que pode gerar cobrança real).
> 3. Corrigir o money path do gate (incluir `fees` e `commissions` no nível forte).
> 4. Ligar branch protection exigindo `ci-gate` verde.
>
> **Por que essa e não outra:** hoje você tem a *ilusão* de proteção — um CI existe,
> mas não roda no lugar certo, não trava nada, e ainda esconde um caminho que pode
> cobrar de verdade na produção. A Fase 0 troca a ilusão por proteção real em poucas
> horas e **risco quase zero** (mudança de configuração, não de lógica). Tudo o mais
> (CI inteligente, gitleaks, CD, rollback) só vale a pena **depois** que o portão
> existe de verdade.

---

## 6. O que eu preciso de você agora

1. **Aprovação do plano** (ou ajustes). Não escrevo nenhum workflow antes disso.
2. **Confirmar a remoção do `webhook_security.py` do InfinitePay** foi intencional
   (achado 2.4.1) — é segurança de money path.
3. Quando chegarmos lá: as decisões da [Seção 4](#4-decisões-que-só-você-pode-tomar)
   (deploy A/B, Caddy/Traefik).

Se você aprovar, sugiro começarmos pela **Fase 0** — e eu te mostro cada mudança antes
de aplicar.
```