.PHONY: install dev dev-api dev-web test test-api

install:
	uv sync
	cd web && pnpm install

dev-api:
	uv run uvicorn src.api.app:app --reload --port 8000

dev-web:
	cd web && pnpm dev

dev:
	cd web && npx concurrently --names "api,web" --prefix-colors "blue,green" \
		"cd .. && uv run uvicorn src.api.app:app --reload --port 8000" \
		"pnpm dev"

test:
	uv run python -m pytest tests/ -x -q

test-api:
	uv run python -m pytest tests/test_api_summaries.py -x -q
