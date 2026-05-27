# COD-73 — Triagem de TODOs vazios: roles / staff / wiki / otp

## Metodologia
Para cada módulo: li o TODO, o código-fonte (`app/`), PRD existente (se houver),
e verifiquei integrações com outros serviços via grep.

## Tabela de decisões

| módulo   | decisão           | justificativa                                                                                                                                                                                                                                                                   | próxima ação                                                                                                     |
|----------|-------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| `roles/` | PRD JÁ ADEQUADO   | O PRD `roles-adequacao.prd.md` já existe e cobre o TODO completo (hardcode → .env, structlog, remover duplicatas, testes). O TODO original diz "SUPERSEDED". O PRD tem Problem, Evidence, Users, Hypothesis, Success Metrics, Scope — falta só reformatar para as 10 seções oficiais. | Reformatar PRD in-place para estrutura de 10 seções (já tem 6 de 10). Nenhuma nova issue necessária.            |
| `staff/` | PRD JÁ ADEQUADO   | O PRD `staff.prd.md` já existe e cobre o TODO ("boss da operação, cadastra hub, define coordenador, saúde dos serviços"). O TODO diz "SUPERSEDED". O PRD tem Problem, Evidence, Users, Hypothesis, Success Metrics, Scope — falta reformatar para 10 seções.                       | Reformatar PRD in-place para estrutura de 10 seções. Nenhuma nova issue necessária.                              |
| `wiki/`  | DESCOMISSIONAR    | `wiki/` NÃO é um módulo de código — é uma pasta de documentação pura (.md files). Não tem `app/`, não tem endpoints, não tem models. Nenhum Python a importa. O TODO original era sobre criar docs *depois* de aprovar código — era instrução de processo, não feature. Já existem 35+ arquivos .md cumprindo esse papel. | Nenhuma issue de SPEC. Manter como diretório de documentação. Se necessário, mover docs para `/docs/` no futuro. |
| `otp/`   | NEEDS PRD         | Serviço completo e VIVO: ~20 arquivos Python, models (otp, pending_notify, rate_limit), integração direta com `auth` (8 arquivos referenciam otp: register, login, recover, check, atomic). Sem PRD — só tem `wiki/otp.md` (informal) e README. O `otp/data/TODO` ("conecte com postgres") é stale — já tem DATABASE_URL e alembic. | Criar SPEC formal de 10 seções em `.claude/prds/otp.prd.md`. Abrir issue child "[SPEC] otp — pronto para review". |

## Observações adicionais

- **otp/data/TODO** ("conecte com postgres"): STALE. O serviço já usa PostgreSQL via `DATABASE_URL` e tem migrações Alembic. O TODO era do setup inicial.
- **wiki/** como "módulo": a triagem original incluiu wiki porque tinha TODO vazio, mas wiki é documentação, não serviço. Não faz sentido criar SPEC de módulo para uma pasta de .md files.
- **roles/ e staff/** já tiveram seus PRDs criados em sessões anteriores. A reformatação para 10 seções é trabalho trivial de TechWriter — não precisa de issue separada, pode ser feito inline nesta ou na próxima sessão.
