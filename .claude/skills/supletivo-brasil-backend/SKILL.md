```markdown
# supletivo-brasil-backend Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill provides a comprehensive guide to the development patterns, coding conventions, and common workflows used in the `supletivo-brasil-backend` Python codebase. It covers how to structure code, implement new features, maintain consistency, and follow best practices for database migrations, API development, observability, security, testing, and documentation. The repository follows conventional commit patterns and modular service-oriented architecture, with a focus on maintainability and clarity.

## Coding Conventions

- **Language:** Python
- **Framework:** None detected (uses standard Python and common libraries)
- **File Naming:** Uses `camelCase` for file names.
  - Example: `userModel.py`, `healthCheck.py`
- **Import Style:** Relative imports are preferred.
  - Example:
    ```python
    from .models import UserModel
    from ..utils.logging import setup_logging
    ```
- **Export Style:** Named exports (explicitly defined in `__all__` when needed).
  - Example:
    ```python
    __all__ = ['UserModel', 'UserSchema']
    ```
- **Commit Messages:** Follows [Conventional Commits](https://www.conventionalcommits.org/) with prefixes like `feat`, `fix`, `docs`, `chore`, `refactor`.
  - Example: `feat(user): add user registration endpoint`

## Workflows

### Add New Database Table
**Trigger:** When introducing a new entity or resource in a service's database  
**Command:** `/new-table`

1. Create or update the model file in `app/models/*.py`.
2. Create or update the schema file in `app/schemas/*.py`.
3. Create an Alembic migration script in `alembic/versions/*.py`.
4. Update service or API logic to use the new model/schema.
5. Add or update tests for the new model/resource in `tests/*.py`.
6. Update documentation in the wiki or service `README.md`.

**Example:**
```python
# app/models/userModel.py
class UserModel(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
```

### Add API Endpoint
**Trigger:** When exposing a new REST endpoint  
**Command:** `/new-endpoint`

1. Create or update the route file in `app/api/*.py` or `app/api/<group>/*.py`.
2. Add or update request/response schemas in `app/schemas/*.py`.
3. Register the route in the router or main API index.
4. Implement or update service logic as needed.
5. Add or update tests for the endpoint.
6. Update documentation in the wiki or service `README.md`.

**Example:**
```python
# app/api/user.py
@router.post("/users")
def create_user(user: UserSchema):
    return user_service.create(user)
```

### Service Scaffold or Migration
**Trigger:** When starting a new microservice or migrating to a new stack  
**Command:** `/scaffold-service`

1. Create baseline directory structure (`app/`, `tests/`, `alembic/`, etc.).
2. Add initial models, schemas, API routes, and config files.
3. Add initial Alembic migration(s).
4. Add `.env.example`, `README.md`, and `Makefile`/`Dockerfile`.
5. Add or update the test suite.
6. Add service documentation to the wiki.

### Add or Update Health and Env
**Trigger:** When ensuring all services have health checks and documented environment variables  
**Command:** `/add-health-env`

1. Add or update `app/api/health.py` (or similar) in each service.
2. Add or update `.env.example` in each service.
3. Update `docker-compose` files to reference health endpoints.
4. Update wiki or RUNBOOK documentation.

**Example:**
```python
# app/api/health.py
@router.get("/health")
def health_check():
    return {"status": "ok"}
```

### Add or Update Observability Stack
**Trigger:** When improving or standardizing logging, metrics, and monitoring  
**Command:** `/add-observability`

1. Add or update logging config (e.g., `structlog`) in each service.
2. Add or update metrics endpoints and instrumentation.
3. Add or update Prometheus/Loki/Grafana config files.
4. Update `docker-compose` to include observability services.
5. Update RUNBOOK or wiki with observability docs.

### Security Hardening and Audit
**Trigger:** When addressing security audit findings or proactively hardening services  
**Command:** `/security-audit`

1. Add or update PII masking utilities and apply to logging.
2. Add or update RBAC checks and role guard logic.
3. Add or update rate limiting (e.g., `slowapi`) configuration.
4. Add or update webhook/IP/HMAC security logic.
5. Document audit results and security policies in the wiki.

**Example:**
```python
# app/utils/pii.py
def mask_pii(data):
    # Mask sensitive fields
    ...
```

### Test Suite Expansion or Fix
**Trigger:** When increasing test coverage, fixing flaky tests, or adding new integration tests  
**Command:** `/add-tests`

1. Add or update test files for new or existing features.
2. Fix flaky or broken tests.
3. Update coverage configs in `pyproject.toml`.
4. Update QA or coverage stats in the wiki.

**Example:**
```python
# tests/userModel.test.py
def test_create_user():
    ...
```

### Documentation and Wiki Update
**Trigger:** When code, infra, or process changes require updated documentation  
**Command:** `/update-docs`

1. Update or create service `README.md`.
2. Update or create wiki pages (architecture, conventions, runbook, etc.).
3. Add or update `.claude/` memory docs.
4. Document new processes, conventions, or audit results.

## Testing Patterns

- **Framework:** Unknown (likely `pytest` or similar)
- **Test File Pattern:** `*.test.ts` (note: this suggests some TypeScript tests, but Python tests are also present as `*.py`)
- **Location:** All tests reside in the `tests/` directory.
- **Typical Structure:** Test files mirror the structure of the application code and cover models, endpoints, and integration flows.

**Example:**
```python
# tests/userModel.test.py
def test_user_creation():
    user = UserModel(name="Alice")
    assert user.name == "Alice"
```

## Commands

| Command             | Purpose                                                   |
|---------------------|-----------------------------------------------------------|
| /new-table          | Add a new database table/model and related schema/migration|
| /new-endpoint       | Implement a new API endpoint with schema and tests        |
| /scaffold-service   | Scaffold a new microservice or migrate to a new stack     |
| /add-health-env     | Add or update health endpoints and environment files      |
| /add-observability  | Add or update observability stack and metrics             |
| /security-audit     | Perform security hardening and document audits            |
| /add-tests          | Add, fix, or expand test coverage                         |
| /update-docs        | Update documentation, wiki pages, and internal conventions|
```
