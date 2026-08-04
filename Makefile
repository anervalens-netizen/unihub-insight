.PHONY: install dev verify lint test build clean

install:
	npm install
	uv sync --project apps/api --all-groups

dev:
	npm run dev

verify:
	npm run verify

lint:
	npm run lint

test:
	npm run test

build:
	npm run build

clean:
	rm -rf node_modules apps/web/node_modules apps/web/dist apps/api/.venv
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
