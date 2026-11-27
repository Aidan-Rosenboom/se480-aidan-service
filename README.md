# se480-aidan-service

Deployed at: https://se480-aidan-service.onrender.com

## Check it

make check

Runs the three lab four checks, this includes ruff checks, the coverage maps, and a requirements.txt audit.

other commands that can be run

make coverage: Just the coverage tests

make audit: just the dependency audit

A clean run means that make check or all of these checks passed without issues, the coverage map was above 85%, ruff passes, and dependencies aren't depricated

## Run it
Open the repository in the configured dev container, then:

    uvicorn app.main:app --reload --port 8000 --no-access-log

Run the sample client against the local service or the deployed service:

    python client/example.py http://127.0.0.1:8000
    python client/example.py https://se480-aidan-service.onrender.com

The client lists users, creates an example user, and repeats the creation to
demonstrate the API's conflict response. A sleeping deployed service may take
a moment to wake up.

## Operate it

### Request IDs and logs

Every response, errors included, carries an `X-Request-ID` header, and every
request writes exactly one JSON line to standard output when its response is
sent:

    {"ts":"2026-11-27T02:12:16.239Z","level":"INFO","request_id":"aidan-test-1","method":"GET","route":"/v1/users/{user_id}","status":404,"duration_ms":11}

- `ts` is UTC, to the millisecond. `duration_ms` is a whole number of
  milliseconds from the request arriving to the response being sent.
- `route` is the route template, not the raw path, so requests group by
  endpoint and no id from a path reaches the log. It is `unmatched` when no
  route matched.
- `level` is `ERROR` for a 5xx and `INFO` for everything else: a 4xx is the
  service working, telling a caller no.
- `/health` and `/metrics` are not logged: Render polls `/health`, and those
  lines would bury the requests users send.
- Any other log record a request produces (the traceback of an unhandled
  error, the warning when Steam does not answer) is also one JSON line, with
  `ts`, `level`, `request_id` and `message`, plus `exc_info` for a traceback.
  It carries the same `request_id`, so one search for the id finds the whole
  story:

      grep '"request_id":"aidan-test-1"' service.log

**Incoming ids are accepted if valid.** A caller or proxy that sends its own
`X-Request-ID` gets that id back and in the log, so it can trace one request
across systems. The id goes straight into the log, so it is accepted only if
it is 8–64 characters of letters, digits, `.`, `_` or `-`; anything else
(a quote or newline that could forge a log line, an oversized value) is
ignored and the service makes its own id, 16 random hex characters.

**uvicorn's access log is off** (`--no-access-log` in the Makefile, the
Dockerfile and the run command above). It would duplicate the request line
without the request id, the route template or the duration, so it is dropped
to keep one line per request.

Find a request by its id in a local run:

    make run 2>&1 | tee service.log
    grep aidan-test-1 service.log

### Health and the platform

`/health` answers 200 with `"status": "ok"` whenever the process is up, and
says enough to tell one run of the service from the next:

    {"status":"ok","started_at":"2026-11-27T02:55:20Z","uptime_seconds":0,"commit":"fa7c984","store":{"users":1,"summaries":0}}

- `started_at` and `uptime_seconds` say when this process started. `commit` is
  the first seven characters of `RENDER_GIT_COMMIT`, which Render sets on every
  deploy, and `unknown` on a local run.
- `store` is how many users and summaries the service holds: counts, never
  contents. The store is in memory, so **a restart is visible from outside**:
  `started_at` moves and both counts fall to zero.
- It stays cheap: it reads two lengths and the clock, and never calls Steam,
  so a Steam outage does not make the platform think the service is down.

Three decisions, recorded here because they live in the Render dashboard:

1. **Health Check Path is `/health`** (Settings → Health Checks). Without it,
   Render only checks that the port accepts a connection, so a service that
   started but cannot answer would still count as healthy.
2. **Notifications are set to Only failure notifications, by email**
   (Settings → Notifications). The default is None, which tells nobody about a
   failed deploy.
3. **Render's health checks are neither logged nor counted.** Render calls
   `/health` every few seconds; those calls are not users. Logged, they would
   bury the request lines; counted, they would add thousands of fast 200s to
   `http_requests_total` and make the SLI look better than what users get.
   `/metrics` is left out for the same reason. Both paths are listed in
   `QUIET_PATHS` in `app/observability.py`.

### Metrics

`/metrics` serves the Prometheus text format. It is kept out of the OpenAPI
schema, like `/health`, and is neither logged nor counted itself.

| Metric | Labels | What it counts |
| --- | --- | --- |
| `http_requests_total` | `route`, `status` | Requests, by route template and status class (`2xx`, `4xx`, `5xx`) |
| `http_request_duration_seconds` | `route` | A histogram of response times. Buckets at 0.05, 0.1, 0.25, 0.5, 1, **2.5** and 5 seconds; 2.5 is the SLO's bound (`docs/slo.md`) |
| `steam_id_conflicts_total` | none | Registrations refused with a 409 because the Steam ID was already registered: the rule the failure that matters turns on |
| `steam_requests_total` | `outcome` | Calls to Steam's events feed: `ok`, `not_found`, `unavailable` or `error`, which tells a Steam outage from a fault here |

Labels are only ever the route template, the status class or a fixed outcome,
never an id or a name: each distinct label value makes a new series, so a
user id as a label would grow one series per user.

The counters live in the process. **They start again from zero on every
restart**, and on Render's free instance, which sleeps after 15 idle minutes,
that is often. A number read from `/metrics` covers only the time since
`started_at` in `/health`.

## Known limits

- **`/metrics` is public.** Anyone with the URL can read the request counts.
  That is fine for this course; in production it would sit behind
  authentication or on a private network.
- **The counters reset on every restart**, so `/metrics` alone cannot measure
  a seven-day SLO window (see `docs/slo.md`).
- **Two registrations for one Steam ID, in flight together, both succeed.**
  The duplicate check and the write are two steps with nothing holding the
  Steam ID between them. `tests/test_concurrency.py` reproduces it on demand
  and is marked as an expected failure until it is fixed. When it happens,
  `steam_id_conflicts_total` does not move: nothing in the service notices.

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
# Lab 4 validation hardening
Shape is validated in [app/models.py](./app/models.py) and rules in
[app/rules.py](./app/rules.py), nowhere else. Each constraint in
[openapi.yaml](./openapi.yaml) is a shared component schema (`GameId`,
`SteamId`, `PersonName`, `SummaryText`, `SummaryTitle`, `UpdateVersion`,
`HttpLink`) with one matching annotated type in `models.py`. Every model field
and route parameter carrying that value uses the type.
[tests/test_validation.py](./tests/test_validation.py) has one case per
constraint.

Spec corrections (the spec was wrong, not the code):
  - `game_id` query parameter: `minimum: 1` does nothing on a string, so any
    string, `""` and `null` included, passed. It is now `GameId`, a positive
    integer written as a string (`^[1-9][0-9]{0,9}$`), which the 400 example
    already promised.
  - The `createUser` 201 example left out the required `user_id`.
  - Request bodies (`RegisterUser`, `PatchNoteSummaryInput`) now say
    `additionalProperties: false`, and the models use `extra="forbid"`. Before
    this, a client could send `created_at` or `summary_id` and have it silently
    dropped.
  - `PatchNoteSummary` no longer `allOf`s the input schema, because the
    input's `additionalProperties: false` would then reject the response's
    `summary_id`. Both list their properties and share the component schemas.
  - `link` and `title` are optional but not nullable: leaving one out is
    fine, sending `null` is a 400.

Rules the schema cannot express (this project has no start/end pair; these
are its cross-field and cross-record rules):
  - a Steam account registers once (409);
  - a summary's `user_id` must name a registered user (404);
  - one summary per user, game, and update version (409);
  - a summary is found only under the `game_id` it was posted for (404).

The user-exists and game-match checks used to be written inline in the router.
They moved to `rules.py`, so each rule is checked in one place.

Running Schemathesis against the Lab 3 code with the hardened spec found 7
failures (for example `steam_id: ""` accepted and `game_id=null` accepted).
Against this code, 1883 generated cases pass.

# Lab 4 changes applied

changes to my openapi.yaml, tests, errors.py, rules.py, most py files in the app directory, and the lab required files. My first review exposed that I needed to solidify my variables in my openapi.yaml file which lead me to modify my errors.py, rules.py, and most of the files in the app directory.

# Lab 4 AI usage
I used claude opus 5.5 to help me learn more about the Validation Hardening section, write some tests, and clean up my repository overall while prioritizing learning from what it found and what it was doing.