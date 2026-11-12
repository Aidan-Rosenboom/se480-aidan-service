"""User-posted patch note summary endpoints."""

from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Response

from app import rules, store
from app.errors import ConflictError, NotFoundError, ProblemDetails
from app.models import PatchNoteSummary, PatchNoteSummaryInput

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
    game_id: str = Query(..., min_length=1),
) -> list[PatchNoteSummary]:
    return [
        summary
        for summary in store.summaries.values()
        if summary.game_id == game_id
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
    if payload.user_id not in store.users:
        raise NotFoundError("No user matched the supplied user_id.")
    try:
        rules.ensure_summary_is_unique(
            store.summaries.values(),
            user_id=payload.user_id,
            game_id=payload.game_id,
            update_version=payload.update_version,
        )
    except ValueError as exc:
        raise ConflictError(
            str(exc),
            conflicts_with={
                "user_id": str(payload.user_id),
                "game_id": payload.game_id,
                "update_version": payload.update_version,
            },
        ) from exc

    summary = PatchNoteSummary(
        summary_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        **payload.model_dump(),
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
    summary_id: UUID,
    game_id: str = Query(..., min_length=1),
) -> PatchNoteSummary:
    summary = store.summaries.get(summary_id)
    if summary is None or summary.game_id != game_id:
        raise NotFoundError("No patch note summary matched the supplied identifier.")
    return summary


@router.delete(
    "/patch-note-summaries/{summary_id}",
    summary="Delete one patch note summary",
    description="Permanently delete a user-posted patch note summary.",
    status_code=204,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
def delete_patch_note_summary(summary_id: UUID) -> Response:
    if summary_id not in store.summaries:
        raise NotFoundError("No patch note summary matched the supplied identifier.")
    del store.summaries[summary_id]
    return Response(status_code=204)
