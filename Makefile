.PHONY: run test link mock client

run:
	python -m uvicorn app.main:app --reload --port 8000

test:
	python -m pytest -q

lint:
	npm run lint:openapi

mock:
	npx --yes @stoplight/prism-cli mock openapi.yaml

test:
	python -m pytest -q
