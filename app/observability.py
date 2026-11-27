"""Lab 5: what the service says about itself while it runs.

One middleware does three things for every request: gives it an id, counts it,
and writes one JSON line when the response is sent. Anything else the request
logs on the "app" logger (a traceback, a warning about Steam) is written as a
JSON line too, with the same request id, so one search finds the whole story. Nothing in this module
knows what the service is for, so it moves between services unchanged; a
counter that belongs to a business rule lives beside that rule.
"""

import functools
import json
import logging
import os
import re
import secrets
import sys
import time
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.routing import compile_path

REQUEST_ID_HEADER = "X-Request-ID"

# A request that matches no route gets this label, never the raw path: paths
# carry ids, and an id can be the only key to someone's data.
UNMATCHED = "unmatched"

# Render polls /health every few seconds once it is the health check path, and
# /metrics is read by whoever is watching. Neither is a user request, so neither
# is logged or counted: they would drown the log and flatter the SLI.
QUIET_PATHS = frozenset({"/health", "/metrics"})

# An incoming X-Request-ID is kept only if it looks like an id. Anything else is
# replaced, because the value goes straight into the log.
_ACCEPTABLE_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")

STARTED_AT = datetime.now(UTC)

# The id of the request being handled, for log records written outside the
# middleware: by a route, by the Steam client, or by the last-resort handler in
# errors.py, which runs after the middleware has returned. Each request runs in
# its own task with its own copy, so two requests in flight never see each
# other's id.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")

REQUESTS = Counter(
    "http_requests_total",
    "Requests handled, by route template and status class.",
    ["route", "status"],
)
DURATION = Histogram(
    "http_request_duration_seconds",
    "Seconds from request received to response sent, by route template.",
    ["route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def fail_startup_if_asked() -> None:
    """Lab 5, task 6: a break the platform can see.

    Set LAB5_FAIL_STARTUP=1 in the service's environment and the next deploy
    refuses to start; remove the variable and deploy again to repair it. The
    variable is read once, at startup, and only the service's owner can set it.
    """
    if os.environ.get("LAB5_FAIL_STARTUP") == "1":
        raise SystemExit("LAB5_FAIL_STARTUP=1: refusing to start, on purpose (Lab 5, task 6).")


def request_id(request: Request) -> str:
    """The id this request was given, or "-" if the middleware never saw it."""
    return getattr(request.state, "request_id", "-")


@functools.lru_cache(maxsize=256)
def _template_regex(template: str) -> re.Pattern:
    return compile_path(template)[0]


def route_template(request: Request) -> str:
    """The matched route as the API declares it, e.g. /v1/users/{user_id}.

    Since FastAPI 0.165, a route added with include_router reports its path
    without the router's prefix (/users/{user_id}), and the private scope key
    that holds the full path is gone by the time the response is sent. The
    OpenAPI document has every full template, so the label comes from there,
    the same way errors._allowed_methods finds them. Routes kept out of the
    schema (/health, /metrics, /) fall back to their own path.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if not path:
        return UNMATCHED
    for template in request.app.openapi()["paths"]:
        if template.endswith(path) and _template_regex(template).match(request.url.path):
            return template
    return path


def log_line(**fields) -> None:
    """One JSON object on one line of standard output, where Render's log view collects it."""
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    sys.stdout.write(json.dumps({"ts": now, **fields}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class JsonLineHandler(logging.Handler):
    """Writes each record on the "app" logger as one JSON line, with the request id."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            fields = {
                "level": record.levelname,
                "request_id": current_request_id.get(),
            }
            # A record may name its method and route (logger.x(..., extra={...})),
            # as the last-resort handler does. Only these two: a field added here
            # is a field that could carry someone's data.
            for name in ("method", "route"):
                if hasattr(record, name):
                    fields[name] = getattr(record, name)
            fields["message"] = record.getMessage()
            if record.exc_info:
                fields["exc_info"] = logging.Formatter().formatException(record.exc_info)
            log_line(**fields)
        except Exception:  # noqa: BLE001 - logging must never break the request
            self.handleError(record)


def configure_logging() -> None:
    """Send the "app" logger's records through JsonLineHandler, once."""
    logger = logging.getLogger("app")
    if not any(isinstance(h, JsonLineHandler) for h in logger.handlers):
        logger.addHandler(JsonLineHandler())
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _record(request: Request, status: int, started: float) -> None:
    elapsed = time.perf_counter() - started
    route = route_template(request)
    REQUESTS.labels(route=route, status=f"{status // 100}xx").inc()
    DURATION.labels(route=route).observe(elapsed)
    log_line(
        level="ERROR" if status >= 500 else "INFO",
        request_id=request_id(request),
        method=request.method,
        route=route,
        status=status,
        duration_ms=round(elapsed * 1000),
    )


async def observe(request: Request, call_next) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request.state.request_id = (
        incoming if _ACCEPTABLE_ID.fullmatch(incoming) else secrets.token_hex(8)
    )
    current_request_id.set(request.state.request_id)
    quiet = request.url.path in QUIET_PATHS
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # The last-resort handler in errors.py runs outside this middleware, so
        # its 500 never comes back through here. Record the request now, then
        # let the exception carry on to that handler, which sets the header.
        if not quiet:
            _record(request, 500, started)
        raise
    response.headers[REQUEST_ID_HEADER] = request.state.request_id
    if not quiet:
        _record(request, response.status_code, started)
    return response


def health_report(store: dict[str, int]) -> dict:
    """What /health returns: still cheap, still 200, and now it says something.

    `store` is counts and never contents: how many, not whose.
    """
    uptime = datetime.now(UTC) - STARTED_AT
    return {
        "status": "ok",
        "started_at": STARTED_AT.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "uptime_seconds": int(uptime.total_seconds()),
        "commit": os.environ.get("RENDER_GIT_COMMIT", "")[:7] or "unknown",
        "store": store,
    }


def metrics_response() -> Response:
    """The Prometheus text format, for a /metrics route kept out of the schema."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def install(app: FastAPI) -> None:
    configure_logging()
    app.middleware("http")(observe)
