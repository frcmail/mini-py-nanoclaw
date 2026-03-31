PYTHON ?= python3

.PHONY: install-dev lint test build run setup-verify check docker-build docker-up docker-down docker-smoke

install-dev:
	$(PYTHON) -m pip install -e .[dev]

lint:
	$(PYTHON) -m ruff check nanoclaw tests

format:
	$(PYTHON) -m ruff format nanoclaw tests
	$(PYTHON) -m ruff check --fix nanoclaw tests

format-check:
	$(PYTHON) -m ruff format --check nanoclaw tests

test:
	$(PYTHON) -m pytest

build:
	$(PYTHON) -m build

run:
	$(PYTHON) -m nanoclaw

setup-verify:
	$(PYTHON) -m nanoclaw.setup --step verify

check: lint test build

docker-build:
	docker compose build
	./container/build.sh local

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-smoke:
	./scripts/docker-smoke.sh
