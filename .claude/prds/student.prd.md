# Serviço `student` — Funil do Aluno

> PRD da Parte B (green-field) do `wiki/PLANO_ADEQUACAO.md`. Fonte da spec: `student/TODO`.
> Convenção: `../CONVENTION.md`. Escopo fechado: **somente o diretório `student/`**.

## Problem
Depois que o `enrollment` conclui a matrícula, não existe nenhuma trilha para o aluno: ninguém coleta os documentos obrigatórios (certificado/histórico, RG, comprovante de endereço, certidão, serviço militar, tipo sanguíneo), não há prova, nem caminho até a emissão e retirada do diploma, nem virada para veterano. Sem isso o ciclo do aluno fica interrompido e a secretaria de educação não tem os documentos exigidos para validar a conclusão.

## Evidence
- Spec explícita do negócio em `student/TODO` (requisito do operador): descreve o funil completo aluno↔coordenador.
- `wiki/PLANO_ADEQUACAO.md` (§Parte B, item 6): `student` é "o maior" e fecha o ciclo do aluno (`enrollment → student`).
- Observação da spec: "podemos ter problema com a secretaria de educação sem isso" (certificado + histórico do último ano são obrigatórios).
- Assumption — métricas operacionais reais (tempo por status, taxa de reprovação) precisam de validação via analytics após o serviço rodar.

## Users
- **Primário — Aluno (autenticado, role `student`):** acabou de ser promovido pela matrícula; precisa enviar documentos (fotos), agendar prova, acompanhar status/pendências e, ao fim, registrar a retirada do diploma. Consulta seus dados a qualquer momento (inclusive PDF dos docs).
- **Primário — Coordenador do polo (autenticado, role `coordinator`):** promove o aluno inserindo dados da plataforma de estudo, corrige a prova e lança resultado, confere comissões/pendências antes de liberar a emissão do diploma.
- **Not for:** candidatos ainda na matrícula (domínio do `enrollment`); cálculo/pagamento de comissões (domínio do `commissions`); armazenamento e OCR/validação bruta dos arquivos (domínio do `documents` + `ai`); emissão física do diploma.

## Hypothesis
Acreditamos que **um serviço `student` com máquina de status do aluno (promoção → documentos validados por IA → prova → diploma → veterano) e integrações via httpx (`documents`, `ai`, `notify`, `commissions`)** vai **fechar o ciclo do aluno após a matrícula** para **alunos e coordenadores de polo**.
Saberemos que acertamos quando **um aluno promovido conseguir percorrer todos os status até "veterano" sem intervenção manual fora dos endpoints previstos, e a comissão do coordenador for gerada automaticamente na virada para veterano.**

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Funil percorrível ponta a ponta | 100% dos status alcançáveis pelos endpoints | teste de integração cobrindo promoção→veterano |
| Validação de doc por IA muda status só se aprovada | 0 status avançado sem aprovação | teste do worker_loop (aprova/rejeita/erro) |
| Comissão do coordenador na virada p/ veterano | 1 chamada idempotente ao `commissions` por aluno | teste de integração com client fake |
| `ruff` + `pytest` (sqlite) verdes | 100% | CI local da sessão |

## Scope
**MVP** — Serviço FastAPI, schema Postgres próprio (`student`), espelhando `lead`/`enrollment` (estrutura) e `asaas`/`infinitepay` (stack):

- **Promoção (`enrollment → student`):** endpoint que o coordenador chama (autenticado, role `coordinator`) inserindo os dados da plataforma de estudo; cria o registro do aluno e inicia a máquina de status.
- **Máquina de status do aluno** (nomes finais a confirmar no `/plan`), cobrindo: aguardando documentos → (validação IA) → liberado p/ prova → prova agendada/corrigida (reprovou ⇒ refaz) → aprovado / aguardando envio de documentação → pendência → aguardando emissão de diploma → aguardando retirada → concluído/veterano.
- **Coleta de documentos** (referência + status, arquivo mora no `documents`): serviço militar (se homem), certificado + histórico (obrigatórios, último ano), tipo sanguíneo, comprovante de endereço (FOTO), documento pessoal/RG (FOTO, RG obrigatório), certidão.
- **Validação assíncrona por IA** via **worker_loop** (espelha `asaas`): só muda status se a IA aprovar; aprovação do conjunto libera a prova.
- **Prova:** liberar agendamento; coordenador lança resultado; reprovação reabre p/ refazer.
- **Diploma:** status de emissão (certificado + histórico) e de retirada; POST com foto do aluno retirando o diploma.
- **Veterano:** ao concluir, atribui role `veterano` (mantendo `student` — multi-role) via `roles`/`auth`, e dispara **comissão** ao `commissions` para o coordenador do polo (chamada assíncrona, idempotente).
- **Consultas:** GET dos dados de matrícula/aluno; GET de pendência; GET geral dos dados a qualquer momento (incluindo versão PDF dos docs, servida pelo `documents`).
- **Notify (§11):** notificação assíncrona nas mudanças de status relevantes (aluno e/ou coordenador) e lembretes para quem ficar parado num status.
- **Conformidade:** API nos 3 tipos (§5), PK UUID + shadow tables read-only cross-schema (§4), integrações só em `integrations/` via `httpx` (§12), IA via app `ai` (§13), simplicidade (§14).

**Out of scope**
- Criar/alterar os tipos de documento dentro do serviço `documents` — outra sessão/PR; aqui entra como **contrato de integração**.
- Implementar `ai`, `notify`, `commissions`, `coordinator`, `enrollment` — consumidos via client httpx, não construídos.
- Lógica de cálculo/pagamento de comissão (só dispara o evento ao `commissions`).
- Emissão real do diploma e geração do PDF (o PDF dos docs vem do `documents`).
- LMS/matérias e correção por IA da prova (domínio do `training`).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Spine + promoção | Coordenador promove o aluno (enrollment→student) e o registro nasce no status inicial; GET dos dados | in-progress | `.claude/PRPs/plans/student-spine-promotion.plan.md` |
| 2 | Documentos + validação IA | Aluno envia os documentos (refs no `documents`); worker_loop valida via `ai`; status só avança se aprovado | pending | — |
| 3 | Prova | Aluno é liberado, agenda; coordenador lança resultado; reprovação reabre | pending | — |
| 4 | Diploma + veterano + comissão | Emissão→retirada, POST foto do diploma, role veterano (multi-role) e comissão ao coordenador | pending | — |
| 5 | Notify + pendências + PDF | Notificações async nos status, GET de pendência, GET geral com PDF dos docs | pending | — |
| 6 | §15 + wiki | `ruff`+`pytest` verdes, checklist §15, `wiki/student.md` (fonte de verdade) e `.claude/` | pending | — |

## Open Questions
- [ ] Contrato do `documents`: quais endpoints/payload o `student` assume para criar/consultar referência de documento e obter o PDF? (define o client `integrations/documents.py`)
- [ ] Contrato do `ai`: qual endpoint de validação de imagem (comprovante de endereço, RG) e formato de resposta aprovado/reprovado? (§13)
- [ ] Contrato do `commissions`: payload e chave de idempotência para "comissão do coordenador na virada para veterano".
- [ ] Atribuição da role `veterano`: é o `student` que chama `roles`/`auth`, ou emite evento? (multi-role, mantém `student`)
- [ ] Nomes finais e ordem exata dos status (enum) — fechar no `/plan`.
- [ ] Tipo sanguíneo: é um campo do aluno (dado) ou um "documento" no `documents`? A spec lista junto dos docs mas é um dado simples.
- [ ] Quem aplica/corrige a prova é sempre o coordenador do polo do aluno (autorização por polo via shadow `hub`)?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Serviços dependentes (`documents`, `ai`, `commissions`, `coordinator`) ainda não existem | Alta | Médio | Clients httpx com contrato assumido + shadow tables; fluxo não quebra se a integração falhar (§12); testes com fakes |
| Validação por IA indisponível/erro deixa aluno travado | Média | Alto | worker_loop idempotente com retry/backoff; status de erro reprocessável; só avança em aprovação |
| Acoplamento indevido (invadir domínio de `documents`/`commissions`) | Média | Alto | §6/§12: armazenar só `external_id`+status; nunca importar model alheio; revisão §15 |
| Escopo "o maior" estourar a sessão | Alta | Médio | Milestones fatiados; 1 commit no fim; § "menos é mais" (§14) |
| Multi-role (veterano + student) inconsistente com `roles`/`auth` | Média | Médio | Confirmar contrato de role antes do milestone 4; não duplicar tabela de roles (§dedup) |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
