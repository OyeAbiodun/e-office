.PHONY: install dev lint format test build

install:
	python -m pip install -e "apps/api[dev]"
	npm --prefix apps/web install

dev:
	docker compose up --build

lint:
	ruff check apps/api
	ruff format --check apps/api
	npm --prefix apps/web run lint
	npm --prefix apps/web run format:check

format:
	ruff check --fix apps/api
	ruff format apps/api
	npm --prefix apps/web run format

test:
	pytest apps/api
	npm --prefix apps/web run test

build:
	npm --prefix apps/web run build

