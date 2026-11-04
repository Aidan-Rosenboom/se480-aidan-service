# se480-aidan-service

Deployed at: https://se480-aidan-service.onrender.com

## Run it
Open the repository in the configured dev container, then:

    uvicorn app.main:app --reload --port 8000

## Test it

    pytest -q

## Run the mock server

After rebuilding the dev container, run this from the repository root:

    npx @stoplight/prism-cli mock openapi.yaml

Prism serves the mock API at `http://127.0.0.1:4010` using the examples and
schemas in [openapi.yaml](./openapi.yaml). With Docker Desktop, make sure the
dev container is running before executing the command. In VS Code, run
**Dev Containers: Rebuild Container** once after pulling this configuration
change so Node.js and `npx` are installed.

## Review changes applied

- Updated [project_design.md](./project_design.md) with seven concrete
  collection/item operations, including Steam patch-note retrieval, user
  sessions, and game-filtered summaries. This answers the review comments
  requesting complete endpoint ideas and clarification that summaries can be
  posted while Steam notes are fetched.
- Added the Problem Details error shape and documented validation (`400`), not
  found (`404`), and conflict (`409`) errors. This answers the review comment
  requesting the error model's shape and three common caller errors.
- Documented the `/v1` path-prefix version policy and marked the three
  highest-risk operations with the people who could be harmed. This answers
  the review comments requesting a compatibility promise and user-focused risk
  marks.
- Added [openapi.yaml](./openapi.yaml) with every operation, parameters,
  schemas, examples, reusable Problem Details responses, and the common errors
  on each operation. This answers the review comment requesting a complete
  OpenAPI contract.
- Added the Redocly OpenAPI lint job in
  [.github/workflows/ci.yml](./.github/workflows/ci.yml). This answers the
  review comment requesting Swagger Editor-style validation in CI.
- Added the Prism command above for the Docker Desktop dev container. This
  answers the review comment requesting a one-command mock server in the
  README.

## What's here
- app/ — the service
- tests/ — the smoke test
- .devcontainer/ — the development environment
- .github/workflows/ci.yml — CI
- openapi.yaml — API contract and Prism mock-server source

## Help received
I did this all myself with help from google and gitlab docs

## AI tools used
Used a bit of google AI and Chat GPT to solve my smoke.sh LF line sequence that caused the smoke test for the deployment to fail, otherwise I stuck to the github docs and the lab handout.
