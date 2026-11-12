"""User endpoints."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response

from app import rules, store
from app.errors import ConflictError, NotFoundError, ProblemDetails
from app.models import User, UserInput

router = APIRouter()
ERROR_RESPONSES = {
    400: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    500: {"model": ProblemDetails},
}


@router.get(
    "/users",
    summary="List users",
    description="Return all users registered with the service.",
    response_model=list[User],
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def list_users() -> list[User]:
    return list(store.users.values())


@router.post(
    "/users",
    summary="Create a user",
    description="Register a user and return the newly created user.",
    status_code=201,
    response_model=User,
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def create_user(
    payload: UserInput,
    request: Request,
    response: Response,
) -> User:
    try:
        rules.ensure_user_does_not_exist(
            store.users.values(),
            steam_id=payload.steam_id,
        )
    except ValueError as exc:
        raise ConflictError(
            str(exc),
            conflicts_with={"steam_id": payload.steam_id},
        ) from exc

    user = User(user_id=uuid4(), **payload.model_dump())
    store.users[user.user_id] = user
    response.headers["Location"] = str(
        request.url_for("get_user", user_id=user.user_id),
    )
    return user


@router.get(
    "/users/{user_id}",
    summary="Get one user",
    description="Return a user identified by their user ID.",
    response_model=User,
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def get_user(user_id: UUID) -> User:
    try:
        return store.users[user_id]
    except KeyError as exc:
        raise NotFoundError("No user matched the supplied identifier.") from exc
