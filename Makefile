.PHONY: run test link mock client

run:
	python -m uvicorn app.main:app --reload --port 8000

test:
	python -m pytest -q

lint:
	npm run lint:openapi

mock:
	npx --yes @stoplight/prism-cli mock openapi.yaml


# Lab 4: the three checks, and the one command that runs them all.

lint-py:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check --fix .

coverage:
	python -m pytest -q --cov=app --cov-report=term-missing

audit:
	pip-audit -r requirements.txt

pin:
	pip-compile --quiet --output-file=requirements.txt requirements.in

check: lint-py coverage audit