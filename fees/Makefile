.PHONY: install test lint format run migrate migrate-down check

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check app/ tests/ alembic/

format:
	uv run ruff format app/ tests/ alembic/

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

check:
	uv run alembic check
