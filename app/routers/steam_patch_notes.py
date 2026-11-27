"""Steam patch-note retrieval endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app import steam
from app.errors import NotFoundError, ProblemDetails, ServiceUnavailableError
from app.models import GameId, SteamPatchNote

log = logging.getLogger("app")
router = APIRouter()
ERROR_RESPONSES = {
    400: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    500: {"model": ProblemDetails},
    503: {"model": ProblemDetails},
}


def get_steam_client() -> steam.SteamClient:
    """The Steam client; tests replace it through app.dependency_overrides."""
    return steam.SteamClient()


@router.get(
    "/steam-patch-notes",
    summary="Fetch patch notes for a game from Steam's API",
    description="Return patch notes retrieved from Steam for a game.",
    response_model=list[SteamPatchNote],
    response_model_exclude_none=True,
    responses=ERROR_RESPONSES,
)
def get_steam_patch_notes(
    game_id: Annotated[GameId, Query()],
    client: Annotated[steam.SteamClient, Depends(get_steam_client)],
) -> list[SteamPatchNote]:
    try:
        return client.major_updates(game_id)
    except steam.GameNotFound as exc:
        raise NotFoundError(str(exc)) from exc
    except steam.SteamUnavailable as exc:
        log.warning("Steam unavailable for game %s: %s", game_id, exc)
        raise ServiceUnavailableError() from exc
