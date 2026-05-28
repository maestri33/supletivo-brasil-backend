# ai — Production Readiness

## Problem
O microserviço `ai/` (gerador genérico de IA: text/image/tts/json/ocr) **sobe e
responde**, mas está "Parcial": tem **zero testes automatizados**, o
**empacotamento quebra** (`pyproject` aponta `readme = "README.md"` que não
existe → `uv build`/imagem Docker falha) e carrega **dois desvios da CONVENTION**
(OCR síncrono bloqueia o event loop; schemas fora da pasta canônica). Deixar
assim significa: regressões sobem sem rede de proteção, o build de produção
falha, e uma única chamada de OCR pode travar todo o serviço async sob carga.

## Evidence
- Inspeção direta do repositório nesta sessão: `import app.main` OK, mas
  `tests/` ausente e nenhuma dep `pytest`/`pytest-asyncio` no `pyproject`.
- `ai/pyproject.toml:5` declara `readme = "README.md"`; o arquivo não existe.
- `ruff check app` → 2 erros (imports não usados: `Request` em `app/api/v1.py:8`,
  `time` em `app/integrations/deepseek.py:9`).
- `app/integrations/ocr.py` usa o SDK `google-cloud-vision` **síncrono**
  (bloqueante) num serviço async.
- `wiki/ai.md` já registra estes gaps (e contém nota **stale** dizendo que há
  aninhamento `ai/ai/app` — já corrigido para `ai/app`).

## Users
- **Primary**: outros microserviços internos da plataforma (lead, candidate,
  notify, …) que consomem os endpoints `/api/v1/*` de IA; e o engenheiro que
  mantém/evolui o serviço `ai`.
- **Not for**: consumidores públicos/externos — o serviço é desmilitarizado
  (interno à plataforma), sem auth própria.

## Hypothesis
We believe **uma suíte de testes smoke+contrato, empacotamento consertado, OCR
async e schemas canônicos** will **tornar o `ai` seguro para deploy e evolução
(regressões detectadas, build de produção válido, sem bloqueio do event loop)**
for **os microserviços consumidores e o mantenedor**.
We'll know we're right when **`ruff` limpo, `uv build` sucesso, `pytest` verde
cobrindo cada endpoint, OCR não-bloqueante, apenas rotas `/api/v1`, e `wiki/ai.md`
atualizado para status "Apto a produção"**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Lint | 0 erros | `uv run ruff check app tests` |
| Empacotamento | sucesso | `uv build` (ou build da imagem Docker) sem erro |
| Cobertura de endpoints | 100% dos endpoints com ≥1 teste happy-path | `pytest` lista por arquivo |
| Suíte | 100% verde | `uv run pytest -q` |
| OCR não-bloqueante | sem chamada sync no event loop | revisão de `integrations/ocr.py` + teste |
| Padronização de rota | só `/api/v1` (0 aliases legados) | `router.py` + teste de rotas |

## Scope
**MVP** — Levar `ai` a "Apto a produção" fechando: (1) empacotamento+lint,
(2) testes smoke+contrato com integrações externas mockadas, (3) OCR migrado para
REST async via `httpx`, (4) schemas consolidados na pasta canônica `schemas/`,
(5) remoção dos aliases de rota legados (só `/api/v1`), (6) `wiki/ai.md` como
fonte de verdade atualizada.

**Out of scope**
- Cobertura profunda de falha/retry por integração (deepseek/gemini/elevenlabs/
  vision) — fica para um passe posterior; o MVP cobre 1 happy-path + validação de
  envelope/erro por endpoint.
- Novas features de IA / novos provedores — não é objetivo deste passe.
- Auth/CORS/rate-limit — o serviço é desmilitarizado; segurança vem em passe
  explícito separado.
- Persistência/DB/Alembic — serviço é stateless por design (correto).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Build & lint verdes | `README.md` existe, `uv build` funciona, `ruff` limpo | pending | — |
| 2 | Suíte de testes | `pytest`+`pytest-asyncio` (`asyncio_mode=auto`), ≥1 happy-path por endpoint com integrações mockadas, 100% verde | pending | — |
| 3 | OCR async | Google Vision via REST `httpx` async; não bloqueia o loop; falha graciosa se a API cair | pending | — |
| 4 | Schemas canônicos | `api/schemas.py` + schemas inline nas rotas consolidados em `app/schemas/` (pasta, §3) | pending | — |
| 5 | Rotas padronizadas | aliases sem `/api/v1` removidos; apenas `/api/v1` exposto | pending | — |
| 6 | Wiki fonte de verdade | `wiki/ai.md` atualizado (remove nota stale de aninhamento; status "Apto a produção"; §15) | pending | — |

## Open Questions
- [ ] **Quem consome os aliases legados** (`/text/`, `/tts/`, `/v1/...`) hoje?
  Confirmar antes de remover (Milestone 5) — risco de quebrar consumidor atual.
- [ ] A **API REST do Google Vision** cobre com paridade o que o SDK usa hoje
  (OCR genérico **e** "document" denso PDF/TIFF)? — validar via docs antes do M3.
- [ ] **Auth do Vision REST**: API key (`GOOGLE_VISION_API_KEY`) basta ou exige
  service-account JSON? Definir variável(is) `.env` (§12).

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Remover alias legado quebra um consumidor não mapeado | Média | Alto | Resolver a open question (grep nos outros serviços) antes do M5; depreciar com aviso se incerto |
| Vision REST não cobrir "document" denso igual ao SDK | Média | Médio | Validar docs no M3; se faltar, manter SDK porém com offload via `anyio.to_thread` como fallback |
| Testes mockados darem falsa confiança (não pegam quebra real de API externa) | Média | Médio | Escopo MVP é contrato/envelope; cobertura de falha/retry fica explicitamente para passe posterior |
| Mudança concorrente da fleet sobre `ai/` durante o trabalho | Baixa | Médio | `ai/` está sem alterações pendentes no git; checar `git status` antes de cada milestone |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
