PYTHON ?= python3

.PHONY: install-dev lint test build run setup-verify check

install-dev:
	$(PYTHON) -m pip install -e .[dev]

lint:
	$(PYTHON) -m ruff check mini_py_nanoclaw tests

test:
	$(PYTHON) -m pytest

build:
	$(PYTHON) -m build

run:
	$(PYTHON) -m mini_py_nanoclaw

setup-verify:
	$(PYTHON) -m mini_py_nanoclaw.setup --step verify

check: lint test build
