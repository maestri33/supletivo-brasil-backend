# Address — Production-Ready

## Problem
O microsserviço `address` é funcional (2 recursos implementados, migração 0001, integrações ViaCEP e webhook prontas), mas **não está apto a produção** pelos critérios da CONVENTION (§4/§9/§15): PK em integer em vez de UUID, ausência total de testes, provisionamento automático de endereço ainda não fechado, e a doc de verdade (`wiki/address.md`) descreve um estado antigo. Enquanto isso, outros serviços (auth, candidate) já começam a depender dele — o custo de deixar assim é dívida que se espalha por consumidores.

## Evidence
- Verificação ao vivo do código (2026-05-24): PK `integer` autoincrement nas 3 tabelas (`addresses`, `entity_address_details`, `entity_addresses`); `external_id` já é UUID.
- Não existe diretório `address/tests/` — zero cobertura.
- `auth/app/integrations/address.py` e `auth/tests/test_register_provision.py` existem como arquivos novos/untracked → o fluxo auth→address está em curso mas não validado/fechado.
- `wiki/address.md` afirma aninhamento `address/address/app/` e `uploads/` versionado — ambos **já resolvidos** na árvore atual (estrutura é `address/app/`, `uploads/` está no `.gitignore`). Doc desatualizada.
- `address/TODO` lista `post /webhook/external_id/ (cria endereco null ... implementar em auth)` como item em aberto.

## Users
- **Primary**: serviços internos da plataforma (auth, candidate, etc.) que consomem `address` por HTTP na zona desmilitarizada, e o engenheiro que mantém o serviço. O gatilho é "preciso ler/gravar endereço de uma entidade com confiança de que o dado e o contrato estão corretos".
- **Not for**: consumidores externos/públicos — todos os endpoints de domínio são desmilitarizados (uso interno).

## Hypothesis
We believe **fechar as pendências de produção do address (identidade UUID, cobertura de testes, provisionamento automático auth→address e normalização de endereço assistida por IA)** will **torná-lo confiável e aderente à CONVENTION para uso cross-service** for **os serviços internos que dependem dele**.
We'll know we're right when **a suíte de testes cobre todos os endpoints e integrações e passa verde, `ruff` está limpo, a migração UUID aplica sem erro, criar usuário no auth provisiona um endereço null automaticamente, e `wiki/address.md` reflete a realidade**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Cobertura de endpoints por teste | 100% dos endpoints dos 2 recursos + health | inventário de rotas × testes; `pytest` verde |
| Lint | 0 erros | `ruff check` + `ruff format --check` no serviço |
| Identidade UUID | 3/3 tabelas com PK UUID | revisão de modelos + migração aplica em banco limpo |
| Provisionamento auth→address | endereço null criado a cada registro | `auth/tests/test_register_provision.py` verde + teste no address |
| Degradação graciosa (ViaCEP/IA) | falha externa nunca quebra create/update | teste simulando indisponibilidade |

## Scope
**MVP** — Tornar `address` apto a produção: (1) migrar PK das 3 tabelas para UUID (referências cross-service usam `external_id`/UUID, então o raio de impacto externo é baixo); (2) suíte de testes cobrindo addresses CRUD, entity get-or-create/cep/proof/unlink, ViaCEP com degradação graciosa, webhook best-effort; (3) validar e fechar o provisionamento de endereço null no registro de usuário (fluxo auth→address); (4) normalização/validação de endereço assistida por IA via o app `ai` (§12), com fallback que nunca bloqueia a operação (§13); (5) atualizar `wiki/address.md` como fonte de verdade — somente após aprovado (§15).

**Out of scope**
- Storage externo (S3/MinIO) para comprovantes — mantém `uploads/` em disco local por enquanto (deploy single-VM); vira milestone futuro.
- Endurecimento de autenticação/origem nos endpoints — postura DMZ atual aceita; passe de segurança explícito fica para depois.
- População de `lat`/`lng` (geocoding) — não solicitado neste ciclo.

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Identidade UUID | Todo registro de endereço usa PK UUID, alinhado à convenção da plataforma | in-progress (código pronto; falta aplicar migração em PG real) | .claude/plans/address-production-ready.plan.md |
| 2 | Comportamento confiável | Todos os endpoints e integrações cobertos por teste; `ruff` limpo | pending | — |
| 3 | Provisionamento automático | Novo usuário ganha endereço null no registro (auth→address), fluxo validado | pending | — |
| 4 | Qualidade de endereço com IA | Endereços normalizados/validados via IA com fallback gracioso | pending | — |
| 5 | Doc fonte-de-verdade | `wiki/address.md` atualizado para refletir a realidade de produção | pending | — |

## Open Questions
- [ ] PK→UUID: há dados em produção a migrar ou banco é greenfield? Define se a migração é recriação limpa ou backfill. **TBD — needs validation com o engenheiro.**
- [ ] IA (§13): qual a tarefa exata? Normalizar texto livre de logradouro? Validar consistência CEP×rua×cidade? Sugerir correções? **TBD — needs validation.**
- [ ] Provisionamento: o endereço null deve ser criado pelo auth chamando `address` (auth→address via httpx), ou o address expõe endpoint dedicado consumido pelo auth? Confirmar o contrato já iniciado em `auth/app/integrations/address.py`.
- [ ] Confirmar que adiar storage externo é aceitável para o deploy single-VM atual.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Migração PK integer→UUID quebra dados/FK | Média | Alto | Refs cross-service usam `external_id` (UUID), não a PK — raio externo baixo; aplicar em banco limpo se greenfield; FK interna `entity_address_details` reescrita na mesma migração |
| Dependência de IA falha em runtime | Média | Médio | Degradação graciosa (§13): IA é enriquecimento, nunca bloqueia create/update; testes cobrem o fallback |
| Contrato auth→address divergente do já iniciado | Média | Médio | Validar `auth/app/integrations/address.py` + test antes de codar; alinhar antes de fechar o item do TODO |
| Edição concorrente do worktree (notify/candidate em refactor) | Baixa p/ address | Médio | `address` está estável (sem edição recente); evitar tocar notify/candidate neste ciclo |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
