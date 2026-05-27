# CLAUDE.md — Memória e regras do microsserviço `jwt`

> Fonte da verdade para você (Claude Code) sobre o serviço `jwt`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/jwt.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: **único serviço autorizado a assinar tokens JWT na plataforma**. Emite,
  renova e publica tokens assinados com **RS256** (chave privada).
- **Não persiste dado em banco** — é um serviço stateless. As chaves (`private.pem`,
  `public.pem`) são geradas automaticamente em disco se faltarem (`_ensure_keys()`).
- **Serviço de infraestrutura crítica** — qualquer mudança aqui afeta toda a
  plataforma. Trate com o dobro de cuidado.
- Schema: **nenhum** (sem banco, sem migrações).

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack (§2).** FastAPI + Pydantic v2 + pydantic-settings + structlog. Sem
   SQLAlchemy/Alembic (não usa banco).
4. **Chaves NUNCA versionadas.** `private.pem` e `public.pem` estão no `.gitignore`.
   Verificado: nunca estiveram no git (`git ls-files`/`git log --all` vazios).
5. **Rotação de chave = invalida todos os tokens.** Só faça com aprovação humana
   explícita e plano de comunicação.
6. **Algoritmo fixo:** RS256. Não mude sem justificativa de segurança aprovada.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| Cripto | `cryptography` (RS256, chaves PEM) |
| JWT | `python-jose` |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
jwt/app/
├── main.py          # FastAPI; lifespan
├── config.py        # Settings (.env) — chave opcional, _ensure_keys() fallback
├── exceptions.py
├── api/             # rotas (emit, verify, refresh, public key)
├── schemas/         # Pydantic v2
├── services/        # lógica de assinatura/verificação
└── utils/           # helpers, stats.py
```

## 5. Ambiente real

- **Tipos de endpoint (§5):** `emit`/`verify`/`refresh` são **desmilitarizados**
  (consumidos internamente). `/public-key` é público (necessário para verificação
  externa de token).
- **Segredos:** `JWT_PRIVATE_KEY` e `JWT_PUBLIC_KEY` no `.env` (opcionais — se
  ausentes, `_ensure_keys()` gera em disco).
- **NUNCA** exponha a chave privada em endpoint público.

## 6. Comandos

```bash
make dev / make run          # uvicorn (sem banco — serviço stateless)
make test                    # uv run pytest -q
make lint / make fmt         # ruff check / format
```

## 7. O que NÃO fazer

- ❌ Commitar `private.pem` ou `public.pem` (`.gitignore`'d — verificado).
- ❌ Rotacionar chave sem aprovação humana (invalida todos os tokens ativos).
- ❌ Expor chave privada em endpoint.
- ❌ Mudar algoritmo de assinatura (RS256).
- ❌ Logar token JWT completo (contém dados de usuário).
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.

---

**Antes de qualquer tarefa**, leia também `wiki/jwt.md` e `CONVENTION.md` (raiz).
