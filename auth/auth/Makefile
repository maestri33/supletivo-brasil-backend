.PHONY: install test lint run migrate check

install:
	uv pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check app/ tests/ alembic/

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

check:
	alembic check
