"""Application exceptions and RFC 9457 problem-details handlers."""

import logging
from http import HTTPStatus
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match, compile_path

from app import observability

log = logging.getLogger("app")

PROBLEM_BASE = "https://api.example.com/problems/"
PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """A model for RFC 9457 problem details."""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None
    conflicts_with: dict[str, Any] | None = None


class Problem(Exception):
    """A problem the service knows how to describe to a caller."""

    slug = "about:blank"
    problem_type = "about:blank"
    status = 500
    title = "Something went wrong"

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class ValidationError(Problem):
    """The request is missing or contains invalid data."""

    slug = "validation-error"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 400
    title = "Validation error"

    def __init__(
        self,
        detail: str = "The request is missing or contains invalid data.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class NotFoundError(Problem):
    """The requested resource does not exist."""

    slug = "not-found"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 404
    title = "Not found"

    def __init__(
        self,
        detail: str = "No resource matched the supplied identifier.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class ConflictError(Problem):
    """The request conflicts with the current resource state."""

    slug = "conflict"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 409
    title = "Conflict"

    def __init__(
        self,
        detail: str = "A resource with the supplied unique value already exists.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class UnauthorizedError(Problem):
    """Authentication is required or the supplied credentials are invalid."""

    slug = "unauthorized"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 401
    title = "Unauthorized"

    def __init__(
        self,
        detail: str = "Supplied credentials are invalid, please try again.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class ForbiddenError(Problem):
    """The authenticated client lacks permission for the operation."""

    slug = "forbidden"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 403
    title = "Forbidden"

    def __init__(
        self,
        detail: str = "The authenticated client is not permitted to perform the operation.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class ServiceUnavailableError(Problem):
    """A required upstream service is unavailable."""

    slug = "service-unavailable"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 503
    title = "Service unavailable"

    def __init__(
        self,
        detail: str = "Steam's API is temporarily unavailable.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


class InternalServerError(Problem):
    """An unexpected server-side failure occurred."""

    slug = "internal-server-error"
    problem_type = f"{PROBLEM_BASE}{slug}"
    status = 500
    title = "Internal server error"

    def __init__(
        self,
        detail: str = "An unexpected server error occurred.",
        **extra: Any,
    ) -> None:
        super().__init__(detail, **extra)


def problem_response(request: Request, problem: Problem) -> JSONResponse:
    """Build a problem-details response from a service problem."""

    body = ProblemDetails(
        type=problem.problem_type,
        title=problem.title,
        status=problem.status,
        detail=problem.detail,
        instance=quote(
            request.url.path,
            safe="/:@-._~!$&'()*+,;=",
        ),
        **problem.extra,
    )
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=problem.status,
        media_type=PROBLEM_MEDIA_TYPE,
    )


_MESSAGES = {
    "timezone_aware": "needs a time zone offset, for example 2026-11-02T14:00:00-06:00",
    "missing": "is required",
    "extra_forbidden": "is not a field this request accepts",
}


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _allowed_methods(request: Request) -> str:
    """Every method the API declares for this path, for the Allow header on a 405.

    Starlette's own Allow header names only the first route it tried, and since
    FastAPI 0.165 routes from include_router are wrapped (in a private class)
    rather than copied into app.routes, so walking app.routes no longer finds
    them. The OpenAPI document is public, cached by FastAPI, and is what the
    contract test checks against openapi.yaml. Plain routes outside the schema
    (/health) are still found by walking app.routes.
    """

    path = request.url.path
    methods: set[str] = set()
    for template, path_item in request.app.openapi()["paths"].items():
        regex, _, _ = compile_path(template)
        if regex.match(path):
            methods |= {method.upper() for method in path_item if method in _HTTP_METHODS}
    for route in request.app.routes:
        route_methods = getattr(route, "methods", None)
        if route_methods and route.matches(request.scope)[0] is not Match.NONE:
            methods |= route_methods
    return ", ".join(sorted(methods))


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def handle_problem(request: Request, exc: Problem) -> JSONResponse:
        return problem_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = [
                str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")
            ]
            errors.append(
                {
                    "field": ".".join(loc) or "body",
                    "message": _MESSAGES.get(
                        err.get("type"),
                        err.get("msg", "is invalid"),
                    ),
                }
            )
        return problem_response(
            request,
            ValidationError(
                "Fix the fields listed under errors and send the request again.",
                errors=errors,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            problem = NotFoundError(
                "There is nothing at this path. The operations are listed at /docs.",
            )
        else:
            problem = Problem(
                str(exc.detail),
            )
            problem.status = exc.status_code
            # RFC 9457: with type about:blank, the title is the HTTP status phrase.
            problem.title = HTTPStatus(exc.status_code).phrase
            problem.problem_type = "about:blank"

        response = problem_response(request, problem)
        response.headers.update(exc.headers or {})
        if exc.status_code == 405:
            response.headers["Allow"] = _allowed_methods(request)
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        # The last resort: anything nobody anticipated. The caller gets the same
        # shape as every other error and none of the internals; the traceback
        # goes to the server log, which is where a person debugging it looks.
        # Note for tests: TestClient re-raises server errors unless created with
        # raise_server_exceptions=False.
        #
        # The log names the route template, never request.url.path: the path of
        # /v1/users/{user_id} carries the id that leads to a person's name and
        # Steam ID. The request id is stamped on the record by observability, and
        # the caller is asked to quote it, which is what finds this traceback.
        route = observability.route_template(request)
        log.exception(
            "unhandled error on %s %s",
            request.method,
            route,
            extra={"method": request.method, "route": route},
        )
        # This handler runs outside the request-id middleware (Starlette's
        # ServerErrorMiddleware wraps every user middleware), so the header the
        # middleware adds to other responses has to be added here.
        request_id = request.scope.get("state", {}).get("request_id")
        response = problem_response(
            request,
            InternalServerError(
                "The service could not complete the request. Try again; if it keeps "
                f"failing, report it and quote request id {request_id or 'from the X-Request-ID header'}."
            ),
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response
