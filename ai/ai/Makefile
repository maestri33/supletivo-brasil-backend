.PHONY: dev run test clean

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf data/public/media/image/* data/public/media/audio/*
