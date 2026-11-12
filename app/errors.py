"""Application exceptions and RFC 9457 problem-details handlers."""

from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

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
}


def _allowed_methods(request: Request) -> str:
    """Return every method any route accepts at this path."""

    methods: set[str] = set()
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match is not Match.NONE:
            methods |= getattr(route, "methods", None) or set()
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
                str(part)
                for part in err.get("loc", [])
                if part not in ("body", "query", "path")
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
            problem.title = "Request not allowed"
            problem.problem_type = "about:blank"

        response = problem_response(request, problem)
        response.headers.update(exc.headers or {})
        if exc.status_code == 405:
            response.headers["Allow"] = _allowed_methods(request)
        return response
