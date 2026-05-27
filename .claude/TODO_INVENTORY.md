# CODE-TODO INVENTORY — 2026-05-27

Gerado por varredura de `grep -rInE '\b(TODO|FIXME|XXX|HACK)\b' --include='*.py' .`
(excluindo .venv, __pycache__, node_modules, .git)

## Resumo

| # | Arquivo | Classificação | Ação |
|---|---------|---------------|------|
| 1 | candidate/app/services/selfie.py:11 | **documented** | Nenhuma — pendência de integração já documentada na PRD candidate |
| 2 | asaas/app/services/config_key.py:113 | **dead (false positive)** | XXX é parte de máscara de CPF (`***.XXX.XXX-**`), não marcador de código |
| 3 | student/app/models/student.py:18 | **documented** | Referência ao spec student/TODO — já documentado na PRD student |
| 4 | auth/app/api/register.py:136 | **documented** | Referência ao auth/TODO — já documentado na PRD auth |
| 5 | commissions/app/integrations/asaas_client.py:63 | **needs spec** | TODO real: chamada real à API Asaas. Bloqueado em credenciais prod. Manter como TODO + linkar PRD commissions |
| 6 | promoter/app/services/commissions.py:3-4 | **documented** | Pendência documentada: serviço commissions não existe ainda (só spec) |
| 7 | promoter/app/schemas/commissions.py:3 | **documented** | Mesma pendência do #6, em schema |
| 8 | promoter/app/integrations/commissions.py:3 | **documented** | Mesma pendência do #6, em integração |

## Classificações

- **resolvable**: pode ser resolvido agora sem dependência externa
- **needs spec**: precisa de spec formal antes de resolver
- **dead**: obsoleto ou falso positivo
- **documented**: já documentado em PRD/spec, referência legítima
- **escala**: precisa de decisão de escopo ou aprovação humana

## Resultado

- **Resolvíveis automaticamente:** 0
- **Needs spec:** 1 (#5 — commissions Asaas API call, bloqueado em credenciais)
- **Dead / false positive:** 1 (#2 — mask pattern)
- **Documented (manter como estão):** 6 (#1, #3, #4, #6, #7, #8)

Nenhum TODO órfão encontrado. Todos são referências legítimas a specs existentes ou dependências documentadas.
