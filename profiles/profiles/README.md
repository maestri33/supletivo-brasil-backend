# Profiles Service

Microsserviço de dados cadastrais — CPF, nome, nascimento, escolaridade.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Status completo — serviço, banco, uptime, integrações |
| `GET` | `/health` | Health check leve (load balancer) |
| `GET` | `/ready` | Readiness probe (verifica banco com `SELECT 1`) |
| `POST` | `/api/v1/profiles` | Cria perfil (`external_id` + `cpf`) |
| `GET` | `/api/v1/profiles` | Lista todos (resumo: `external_id`, `cpf`, `name`) |
| `GET` | `/api/v1/profiles/{external_id}` | Detalhe completo com educational + birth_info |
| `PATCH` | `/api/v1/profiles/{external_id}` | Atualização parcial tipada — envia só os campos que quer alterar |
| `DELETE` | `/api/v1/profiles/{external_id}` | Remove perfil em cascata (Profile + Educational + BirthInfo) |
| `GET` | `/api/v1/profiles/cpf/{cpf}` | Busca por CPF — retorna `found`, `valid`, `external_id` |
| `GET` | `/api/v1/profiles/first-name/{external_id}` | Retorna primeiro nome |

### PATCH — Atualização parcial

Envie apenas os campos que deseja alterar. Use `null` para limpar um campo.

```json
PATCH /api/v1/profiles/abc-123
{
  "name": "Victor Maestri",
  "gender": "M",
  "city": "São Paulo",
  "birth_date": "1990-06-15",
  "level": "higher_complete",
  "elementary_completed": true
}
```

Campos não enviados **não são alterados**. Campos desconhecidos são **rejeitados** (422).

## Entidades

### Profile

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `external_id` | `str(36)` | Sim (criação) | Imutável após criação |
| `cpf` | `str(11)` | Sim (criação) | Dígitos verificadores, imutável |
| `name` | `str(200)` | Não | Normalização completa + validação (ver abaixo) |
| `gender` | `str(1)` | Não | Aliases: `M`/`F`/`male`/`female`/`masculino`/`feminino`/`homem`/`mulher` |
| `mother_name` | `str(200)` | Não | Mesma validação de nome |
| `father_name` | `str(200)` | Não | Mesma validação de nome |
| `blood_type` | `str(3)` | Não | Aliases: `A+`/`a positivo`/etc. (8 tipos ABO+Rh) |
| `civil_status` | `str(20)` | Não | Aliases: `single`/`solteiro`/`married`/`casado`/`widowed`/`viúvo`/`divorced`/`divorciado`/`stable_union`/`união estável` |
| `description` | `text` | Não | Máx 2000 chars, sem markup/emojis |

### Educational (1:1 com Profile)

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `level` | `str(30)` | Não | Enum: `elementary_incomplete`, `elementary_complete`, `high_school_incomplete`, `high_school_complete`, `higher_incomplete`, `higher_complete` |
| `last_elementary_year` | `str(10)` | Não | Enum: `pre`, `1st`..`9th` |
| `elementary_completed` | `bool?` | Não | Aceita `true`/`false`/`1`/`0`/`yes`/`no`/`sim`/`não` (vazio = `null`) |
| `elementary_year` | `int?` | Não | Range 1900..ano atual |
| `last_high_school_year` | `str(15)` | Não | Enum: `1st_hs`, `2nd_hs`, `3rd_hs` |
| `high_school_completed` | `bool?` | Não | Igual `elementary_completed` |

### BirthInfo (1:1 com Profile)

| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| `state` | `str(2)` | Não | UF brasileira (27 siglas) |
| `city` | `str(100)` | Não | Normalização + validação (máx 100, sem markup/emojis, min 2 letras) |
| `birth_date` | `date?` | Não | ISO 8601, passado, idade >= 16 anos |

## Pipeline de validação de nome

Todos os campos de nome (`name`, `mother_name`, `father_name`) passam por:

1. **Unicode NFC** — caracteres combinados normalizados (João → João)
2. **Remoção de invisíveis** — zero-width space, RTL, controles, BOM, soft hyphen
3. **Colapso de whitespace** — tabs, newlines, espaços duplos → espaço simples
4. **Trim**
5. **Capitalização inteligente** — conectivos minúsculos (da, de, do, das, dos, e), preserva hífens (Ana-Clara) e apóstrofos (D'Ávila, O'Connor)

Regras de rejeição (422):
- Máximo 120 caracteres
- Mínimo 2 letras Unicode
- Bloqueia apenas números/símbolos
- Bloqueia emojis, markup (`<script>`, `<>{}`), SQL-ish
- Bloqueia separadores consecutivos (`--`, `''`)
- Blacklist: `admin`, `root`, `system`, `null`, `undefined`, `suporte`, `test`, `usuario`, `ninguem`, `anônimo`, `cliente`, `visitante`
- Nonsense: repetição >50%, padrão periódico (ababab)

### Normalização de cidade

Mesma pipeline de nome para o campo `city` (trim, invisíveis, colapso, Title Case com conectivos minúsculos).

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SERVICE_NAME` | `profiles-service` | Nome do serviço |
| `ENV` | `dev` | Ambiente (`dev`, `staging`, `prod`) |
| `LOG_LEVEL` | `INFO` | Nível de log |
| `PORT` | `80` | Porta do servidor |
| `DATABASE_URL` | `sqlite://data/profiles.db` | URL de conexão do banco |
| `CORS_ORIGINS` | `*` | Origins permitidas (separadas por vírgula) |
| `INTEGRATIONS` | `{}` | JSON com nome → URL dos serviços integrados |

## Arquitetura

```
app/
├── api/            # Rotas FastAPI
│   ├── profiles.py # CRUD de Profile
│   ├── health.py   # /, /health, /ready
│   └── router.py   # Agregador
├── models/         # Tortoise ORM
│   ├── profile.py
│   ├── educational.py
│   └── birth_info.py
├── schemas/        # Pydantic (contratos de entrada/saída)
│   └── profile.py
├── services/       # Lógica de domínio
│   └── profile_service.py
├── validators/     # Normalização + validação por campo
│   ├── name.py           # normalize_name, validate_name, canonicalize_name
│   ├── profile_fields.py # validate_gender, validate_blood_type, validate_civil_status
│   ├── educational.py    # validate_level, validate_elementary_year, normalize_boolean, etc.
│   ├── description.py    # normalize_description, validate_description
│   ├── location.py       # validate_state, normalize_city, validate_city
│   ├── birth_date.py     # normalize_birth_date, validate_birth_date
│   └── cpf.py            # validate_cpf
├── config.py       # Settings (pydantic-settings)
├── db.py           # Conexão Tortoise
├── exceptions.py   # DomainError, NotFound, Conflict, ValidationError, IntegrationError
└── main.py         # Entrypoint FastAPI
```

### Separação de camadas

- **Normalizer** (`normalize_*`) — limpeza, sempre aplicada, nunca rejeita
- **Validator** (`validate_*`) — regras de domínio, rejeita com `ValidationError`
- **Canonicalizer** (`canonicalize_*`) — representação interna para dedup/busca (não afeta display)

## Testes

```bash
.venv/bin/pytest tests/ -v
```

131 testes cobrindo CRUD completo, validação de nome, descrição, cidade, dados educacionais, data de nascimento, aliases de enums, e casos de rejeição.
