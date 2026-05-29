# Pull Request

## Serviço(s) afetado(s)

<!-- marque os serviços tocados por este PR -->
- [ ] address
- [ ] ai
- [ ] asaas
- [ ] auth
- [ ] candidate
- [ ] commissions
- [ ] coordinator
- [ ] documents
- [ ] enrollment
- [ ] fees
- [ ] hub
- [ ] infinitepay
- [ ] jwt
- [ ] lead
- [ ] notify
- [ ] otp
- [ ] profiles
- [ ] promoter
- [ ] roles
- [ ] staff
- [ ] student
- [ ] training
- [ ] infra (docker-compose, CI, docs transversais)

## O que este PR faz

<!-- descrição breve e clara do que mudou e por quê. Referencie issue se existir. -->


## Tipo de mudança

- [ ] Feature (funcionalidade nova)
- [ ] Fix (corrige bug)
- [ ] Refactor (sem mudança de comportamento)
- [ ] Docs (só documentação)
- [ ] Infra (Docker, CI, scripts)
- [ ] Migration (migração Alembic)

## Checklist de conformidade (CONVENTION.md §15)

<!-- o autor marca antes de pedir review; o reviewer confirma -->

- [ ] **Stack** — usa só a stack canônica (§2)? Nenhuma lib proibida/sem justificativa?
- [ ] **Postgres** — async (`asyncpg`/`AsyncSession`)? Schema próprio? Migração Alembic criada quando o modelo mudou?
- [ ] **Relacionamento** — FK cross-schema via shadow table, sem importar model alheio (§4)?
- [ ] **Diretórios** — cada arquivo no lugar certo? `api/`, `models/`, `schemas/`, `services/` (pastas)?
- [ ] **Fronteira** — alteração dentro da responsabilidade do serviço, sem invadir domínio alheio (§5)?
- [ ] **Idioma** — identificadores em inglês; docstrings/comentários em pt-br e verdadeiros (§6)?
- [ ] **Ruído** — nada de `__pycache__`/órfãos/código morto/duplicação de config (§8)?
- [ ] **Duplicação** — não repete lógica existente; reusa util/service (§9)?
- [ ] **Ferramentas** — usa DI, Pydantic v2, SQLAlchemy 2.0, structlog, httpx corretamente (§7)?
- [ ] **Documentação** — `wiki/<app>.md` atualizado (fonte de verdade)? README/docstrings condizem?
- [ ] **Testes & lint** — há teste para o comportamento novo? `ruff check` + `ruff format` limpos?
- [ ] **TODOS** — nenhum TODO/FIXME/XXX órfão? Todos resolvidos ou justificados?

## Notas para o reviewer

<!-- pontos de atenção, trade-offs, decisões de design que merecem olhar mais de perto -->


## Screenshots / logs

<!-- se aplicável, cole logs relevantes ou screenshots -->
