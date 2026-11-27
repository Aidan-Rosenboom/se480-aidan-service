# Lab 5 kickstart: pick up where the last session left off

Paste the prompt below into a new Claude Code session in this repo. The prompt
is written for the assistant, so the rest of this file is the background it
needs.

---

## Prompt

> I'm working on Lab 5 for this service (observability, SLO, alerts, a
> deliberate failure, and a postmortem). Due Nov 22, 2026 11:59 pm, with a
> 48-hour grace period. An earlier session already built step 1 (request ids
> and one JSON log line per request). That work is uncommitted on branch
> `lab_5_real`. Read `LAB5_KICKSTART.md` for what was done, the decisions made
> and the gotchas found.
>
> I now have the course's reference/template material for `observability.py`
> and related pieces: **[paste or point to it here]**. Before writing anything
> new:
> 1. Compare the existing `app/observability.py`, the `app/errors.py` change
>    and `tests/test_observability.py` against the reference. List where they
>    differ in structure, naming, field names or behaviour, and recommend
>    whether to adopt the reference's shape. Don't change anything until I
>    agree.
> 2. Then we'll go through the remaining lab steps one at a time. I'll paste
>    each step's text as we reach it. Don't jump ahead.
>
> `make check` must stay clean (ruff, ruff format, coverage ≥ 85%, pip-audit).

---

## Lab overview (from the handout)

What a finished repository looks like:

- `make check` runs clean in a fresh Codespace.
- Five requests sent to a local run can each be found in the output by the id
  in their `X-Request-ID` header.
- `/health` and `/metrics` on the deployed URL report what tasks 3 and 4 ask
  for. Those tasks haven't been pasted yet.
- Render is set to alert when a deploy or the service fails. This is set up in
  the Render dashboard, by the user.
- The service is broken on purpose to see which signals notice.
- `docs/slo.md` and `docs/postmortem.md` read as finished documents. Both are
  currently **empty**.
- The README has an **Operate it** section. It has been started and covers
  only request ids so far.
- The Milestone 2 requirements, due at the same time, are in a section of the
  handout that hasn't been pasted yet.

## Step 1 as given

> Middleware gives every request an id, returns it in an X-Request-ID response
> header, and writes exactly one JSON object on one line to standard output
> when the response is sent: ts (UTC), level, request_id, method, route,
> status, duration_ms. The id is on every response, errors included, and in
> every log record the request produces. Decide whether you accept an incoming
> X-Request-ID or always make your own, and say which in the README; validate
> an id you accept. Turn uvicorn's access log off, or say why you kept both.
> Then send a mix of requests at a local run and answer from the output alone:
> which was slowest, how many ended 4xx, and what happened to the one whose id
> you kept.

## What was built (uncommitted)

| File | Change |
|---|---|
| `app/observability.py` | New. A pure ASGI `RequestLogMiddleware`; a `JsonFormatter`; a `RequestIdFilter` on the `app` logger that stamps `request_id` from a `ContextVar`; `install(app)` |
| `app/main.py` | `observability.install(app)` after `errors.install(app)`. The file uses CRLF line endings, so keep them |
| `app/errors.py` | `handle_unexpected` copies `scope["state"]["request_id"]` into the `X-Request-ID` header |
| `tests/test_observability.py` | Renamed from the misspelled, empty `tests/text_observability.py`. Covers the header and the line on 200/400/404/405/500, the route template, kept and replaced ids, and the traceback carrying the id |
| `Makefile`, `Dockerfile`, `README.md` | `--no-access-log` added to each uvicorn command |
| `README.md` | New `## Operate it` → `### Request IDs and logs` section, placed before `## Test it`. The file uses CRLF line endings |

Untouched and still empty: `tests/test_concurrency.py`, `docs/slo.md`,
`docs/postmortem.md`. The `/metrics` route in `main.py` is a stub returning
JSON. `prometheus-client==0.26.0` is already pinned in `requirements.txt`.

## Decisions made

- **Incoming `X-Request-ID` is accepted** if it fully matches
  `[A-Za-z0-9._-]{1,64}`; otherwise the service generates `uuid4().hex`.
- **`route` is the template**, e.g. `/v1/users/{user_id}`, and `null` when no
  route matched.
- **`level` follows the status:** `info` below 400, `warning` for 4xx, `error`
  for 5xx.
- **Other log records** (on the `app` logger) are JSON with `ts`, `level`,
  `request_id`, `logger`, `message`, plus `exc_info` when present.
- **uvicorn's access log is off.**

## Gotchas found (worth keeping whatever the reference does)

1. **500s bypass user middleware.** Starlette's `ServerErrorMiddleware` wraps
   every added middleware, and the `@app.exception_handler(Exception)` handler
   runs there. The middleware therefore logs status 500 in a `finally` and lets
   the exception propagate, and `handle_unexpected` adds the header itself.
   Test it with `TestClient(app, raise_server_exceptions=False)`.
2. **FastAPI 0.165 drops the router prefix.** `scope["route"].path` is
   `/users/{user_id}`, not `/v1/users/{user_id}`, for `include_router` routes.
   The private `scope["effective_route_context"]` holds the full path but is
   removed after the request, so don't use it. The current fix matches the
   route against the `app.openapi()["paths"]` templates, like
   `errors._allowed_methods` does.
3. **`caplog` formats records after the request has finished**, so the request
   id has to be stamped on the record when it's logged (the filter), not read
   from the ContextVar inside the formatter.
4. **CRLF files** (`main.py`, `README.md`, `Dockerfile`): editing them with
   Python `open()` in text mode converts them to LF and shows the whole file
   as changed in the diff.
5. **`scripts/smoke.sh`** (CI deployed-smoke) checks `/health` for
   `"status":"ok"`. Keep that string exactly when `/health` grows.
6. **Render start command:** check whether the Render dashboard overrides the
   Dockerfile `CMD`. If it does, it needs `--no-access-log` too.

## Step 1 local-run result (already done once)

Nine requests: 200, 200, 201, 409 (kept id `aidan-test-1`), 400, 404, 404
(unmatched), 405, and 200 (malformed id, replaced). From the log alone:

- **Slowest:** the first `GET /health`, at 52 ms (the first request after
  startup).
- **4xx count:** 5.
- **`aidan-test-1`:** a `POST /v1/users` that got a 409 conflict, because the
  user already existed, in 0.67 ms.

Rerun this after any changes made to match the reference:

    python -m uvicorn app.main:app --port 8000 --no-access-log > service.log 2>&1
    grep '^{' service.log | jq -s 'max_by(.duration_ms)'
    grep '^{' service.log | jq -s '[.[]|select(.status>=400 and .status<500)]|length'
    grep aidan-test-1 service.log

## Ideas noted for later steps (not yet agreed)

- `/metrics`: have the same middleware record a Prometheus counter and a
  latency histogram labelled by method, route template and status, and serve
  `prometheus_client.generate_latest()` with its content type.
- SLO: an availability or latency target that can be computed from those
  metrics, naming the metric in `docs/slo.md`.
- Deliberate failure and postmortem: a Steam upstream outage (503s) is a
  likely candidate.
