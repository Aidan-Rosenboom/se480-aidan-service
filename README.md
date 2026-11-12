# se480-aidan-service

Deployed at: https://se480-aidan-service.onrender.com

## Run it
Open the repository in the configured dev container, then:

    uvicorn app.main:app --reload --port 8000

Run the sample client against the local service or the deployed service:

    python client/example.py http://127.0.0.1:8000
    python client/example.py https://se480-aidan-service.onrender.com

The client lists users, creates an example user, and repeats the creation to
demonstrate the API's conflict response. A sleeping deployed service may take
a moment to wake up.

## Test it

  python -m pytest -q

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

# Lab 3 swagger docs
I did not end up changing much in my swagger documentation, the screen reader performed well reading the documentation and I could follow along nicely.

# Changes Applied Lab 3
  - Added Models for most of my endpoints (except auth which I decided would be better for v2)
  - Added error handling with human readable descriptions
  - Added rules for unique users and unique summaries
  - Added the routes to my endpoints in the users, patch_notes_summaries and steam_patch_notes router files
  - Configured my store for some basic patch note / patch note summary storage 
  - Addded scheathesis.tomland MakeFile
  - Edited openapi.yaml to remove v2 session / auth endpoints.

# AI tools used
Copilot Fusion from GHCP (GitHub Copilot) to help with scaffolding of the routers, models, and errors. I then went in to these files myself and tweaked the design to my liking.

Copilot also helped a lot with the writing of the test contract and the unit tests. I reviewed all of the tests written and made sure they were up to my standards before submitting.