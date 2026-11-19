"""Steam patch-note retrieval endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query

from app.errors import ProblemDetails
from app.models import GameId, SteamPatchNote

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
) -> list[SteamPatchNote]:
    return [
        SteamPatchNote(
            game_id=game_id,
            text_content="Improved matchmaking and fixed crash issues.",
            link=(f"https://store.steampowered.com/news/app/{quote(game_id, safe='')}"),
            title="Maintenance update",
            update_version="2026.11.04",
            published_at=datetime(2026, 11, 4, 3, 30, tzinfo=UTC),
        ),
    ]
