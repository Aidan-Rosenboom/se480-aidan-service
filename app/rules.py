"""Framework-free business rules for the service."""

from collections.abc import Iterable
from uuid import UUID

from app.models import PatchNoteSummary, User


def ensure_user_does_not_exist(
    users: Iterable[User],
    *,
    steam_id: str,
) -> None:
    if any(user.steam_id == steam_id for user in users):
        raise ValueError("A user with the supplied Steam ID already exists.")


def ensure_summary_is_unique(
    summaries: Iterable[PatchNoteSummary],
    *,
    user_id: UUID,
    game_id: str,
    update_version: str,
) -> None:
    if any(
        summary.user_id == user_id
        and summary.game_id == game_id
        and summary.update_version == update_version
        for summary in summaries
    ):
        raise ValueError(
            "A summary for this user, game, and update already exists.",
        )