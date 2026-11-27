"""User-posted patch note summary endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Query, Request, Response

from app import rules, store
from app.errors import ConflictError, NotFoundError, ProblemDetails
from app.models import GameId, PatchNoteId, PatchNoteSummary, PatchNoteSummaryInput, Uuid

router = APIRouter()
ERROR_RESPONSES = {
    400: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    500: {"model": ProblemDetails},
}


@router.get(
    "/patch-note-summaries",
    summary="List patch note summaries for a game",
    description="Return user-posted patch note summaries for a game.",
    response_model=list[PatchNoteSummary],
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def list_patch_note_summaries(
    game_id: Annotated[GameId, Query()],
    patch_note_id: Annotated[PatchNoteId | None, Query()] = None,
) -> list[PatchNoteSummary]:
    return [
        summary
        for summary in store.summaries.values()
        if summary.game_id == game_id
        and (patch_note_id is None or summary.patch_note_id == patch_note_id)
    ]


@router.post(
    "/patch-note-summaries",
    summary="Create a user-posted patch note summary",
    description="Create and return a user-posted patch note summary.",
    status_code=201,
    response_model=PatchNoteSummary,
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def create_patch_note_summary(
    payload: PatchNoteSummaryInput,
    request: Request,
    response: Response,
) -> PatchNoteSummary:
    try:
        rules.ensure_user_exists(store.users, user_id=payload.user_id)
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    try:
        rules.ensure_summary_is_unique(
            store.summaries.values(),
            user_id=payload.user_id,
            game_id=payload.game_id,
            update_version=payload.update_version,
            patch_note_id=payload.patch_note_id,
        )
    except ValueError as exc:
        conflicts_with = {
            "user_id": str(payload.user_id),
            "game_id": payload.game_id,
            "update_version": payload.update_version,
        }
        if payload.patch_note_id is not None:
            conflicts_with["patch_note_id"] = payload.patch_note_id
        raise ConflictError(str(exc), conflicts_with=conflicts_with) from exc

    summary = PatchNoteSummary(
        summary_id=uuid4(),
        created_at=datetime.now(UTC),
        **payload.model_dump(exclude_unset=True),
    )
    store.summaries[summary.summary_id] = summary
    response.headers["Location"] = str(
        request.url_for(
            "get_patch_note_summary",
            summary_id=summary.summary_id,
        )
    )
    return summary


@router.get(
    "/patch-note-summaries/{summary_id}",
    summary="Get one patch note summary for a game",
    description="Return a patch note summary identified by its summary ID.",
    response_model=PatchNoteSummary,
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def get_patch_note_summary(
    summary_id: Uuid,
    game_id: Annotated[GameId, Query()],
) -> PatchNoteSummary:
    try:
        return rules.find_summary_for_game(
            store.summaries,
            summary_id=summary_id,
            game_id=game_id,
        )
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc


@router.delete(
    "/patch-note-summaries/{summary_id}",
    summary="Delete one patch note summary",
    description="Permanently delete a user-posted patch note summary.",
    status_code=204,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
def delete_patch_note_summary(summary_id: Uuid) -> Response:
    if summary_id not in store.summaries:
        raise NotFoundError("No patch note summary matched the supplied identifier.")
    del store.summaries[summary_id]
    return Response(status_code=204)
