# Relatório de Sincronização — Microsserviço JWT

**Data:** 2026-05-22
**Fonte de verdade (externo):** `root@10.1.30.20:/opt/v7m/services/jwt/`
**Código local (atualizado):** `/home/maestri33/backend/jwt/jwt/`

O código local estava desatualizado. Este relatório documenta as diferenças
encontradas, as alterações aplicadas para alinhá-lo à fonte de verdade e o
resultado do teste de ponta a ponta com dados reais (sem mock).

---

## 1. Visão geral das diferenças (nível de arquivo)

Comparação recursiva (`diff -rq`), ignorando artefatos e segredos locais
(`__pycache__`, `jwt.egg-info/`, `.env`, `private.pem`, `public.pem`):

| Arquivo | Situação antes | Ação |
|---|---|---|
| `app/api/health.py` | Conteúdo divergente | **Atualizado** |
| `app/config.py` | Conteúdo divergente | **Atualizado** |
| `Dockerfile` | Ausente no local | **Adicionado** (cópia exata do remoto) |
| Demais arquivos `app/**`, `pyproject.toml`, `README.md`, `.env.example`, `.gitignore` | Idênticos | Sem alteração |

Após as alterações, `diff -rq` entre local e remoto retorna **vazio** — o código
está coeso com a fonte de verdade.

---

## 2. Alterações aplicadas (detalhe)

### 2.1 `app/api/health.py`

**(a) Endpoint `/ready` — padronização da resposta**

```diff
 @router.get("/ready")
 async def ready() -> dict:
-    return {"status": "ready"}
+    return {"status": "ok", "service": _settings.service_name}
```

**(b) Novo endpoint `/status`** (resumo de runtime, convenção v7m):

```python
@router.get("/status")
async def status() -> dict:
    """Resumo de runtime — alias enxuto da raiz para a convenção v7m."""
    stats = get_stats()
    return {
        "status": "ok",
        "service": _settings.service_name,
        "version": "1.0.0",
        "environment": _settings.env,
        "uptime_seconds": int(stats.uptime_seconds),
        "tokens_issued": stats.tokens_issued,
        "tokens_refreshed": stats.tokens_refreshed,
    }
```

> Os símbolos usados (`_settings`, `get_stats`) já estavam importados no arquivo
> local, então nenhuma alteração de import foi necessária.

### 2.2 `app/config.py`

Porta padrão alinhada à convenção v7m (8000):

```diff
-    port: int = 80
+    port: int = 8000
```

> Observação: `settings.port` **não é referenciado em lugar nenhum** do código
> (`grep -rn "\.port" app/` → nada). A porta efetiva é definida no `launch` do
> uvicorn (no `Dockerfile`: `--port 8000`). A mudança é apenas para coerência
> com a fonte de verdade; não altera o runtime.

### 2.3 `Dockerfile` (novo)

Copiado byte-a-byte do remoto. Pontos relevantes:
- Base `python:3.12-slim` + `uv` para instalar dependências.
- Usuário não-root `appuser`, volume `/keys`, chaves em `/keys/{private,public}.pem`.
- `EXPOSE 8000` e `HEALTHCHECK` batendo em `/health`.
- `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.

---

## 3. Inconsistência herdada da fonte de verdade

A própria fonte de verdade é **internamente inconsistente** quanto à porta:

- `.env.example` (e o `.env` local) → `PORT=80`
- `app/config.py` (default) e `Dockerfile` → `8000`

Como `settings.port` não é usado, isso não afeta o comportamento, mas é um ponto
a corrigir no upstream para evitar confusão. **Não alterei** `.env`/`.env.example`
porque eles já são idênticos ao remoto — alterá-los criaria nova divergência com
a fonte de verdade.

---

## 4. Artefatos locais não tocados

Existentes apenas no local (não fazem parte do código-fonte):
`.env`, `private.pem`, `public.pem`, `jwt.egg-info/`. Mantidos como estão.

---

## 5. Teste de ponta a ponta (sem mock, dados reais)

Ambiente: venv isolado em `/tmp/jwt_venv` (Python 3.13.5) com dependências reais
do `pyproject.toml`. Servidor real via `uvicorn app.main:app` em `127.0.0.1:8000`,
usando as chaves RSA reais (`private.pem`/`public.pem`). Os tokens foram
verificados criptograficamente (RS256) contra a chave pública publicada no JWKS.

**Resultado: 18 PASS / 0 FALHOU**

Cobertura:
- `GET /health`, `/ready` (formato novo), `/status` (endpoint novo), `/` (dashboard).
- `GET /.well-known/jwks.json` → 1 chave RSA.
- `POST /api/v1/tokens/issue` com `external_id` + `roles` reais → 200.
- Verificação **criptográfica real** RS256 do access token contra a chave do JWKS.
- Claims corretos (`external_id`, `roles`, `type=access`, `iss=jwt`).
- Detecção de adulteração: token alterado é rejeitado.
- `POST /api/v1/tokens/refresh` → 200, novo par preserva claims.
- Erros: refresh com access token → 422 `validation_error`; refresh com lixo →
  422 `validation_error`; issue com `roles` vazio → 422 (schema).
- `/status` reflete contadores reais após atividade (`tokens_issued`/`tokens_refreshed`).

Script do teste: `/tmp/jwt_e2e.py`.

---

## 6. Observação técnica (comportamento da fonte de verdade)

Os tokens são emitidos **sem o header `kid`** (`jwt.encode` sem `headers={"kid": ...}`),
embora o JWKS publique um `kid` (sha256 da chave pública). Consequência: clientes
JWKS que selecionam a chave por `kid` (ex.: `PyJWKClient`) **não conseguem casar a
chave automaticamente**. A verificação funciona porque há uma única chave publicada.

Isto é comportamento atual da fonte de verdade — não foi alterado. Recomendação
para o upstream: incluir `kid` no header dos tokens, casando com o `kid` do JWKS,
para compatibilidade com clientes JWKS padrão.
