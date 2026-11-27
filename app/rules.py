"""Framework-free business rules for the service.

These are the rules openapi.yaml cannot express because they depend on more
than one field or on stored data. Shape (types, lengths, patterns) belongs in
app/models.py; do not repeat it here.

Rules raise ValueError when the request conflicts with stored data (409) and
LookupError when it refers to something that does not exist (404).
"""

from collections.abc import Iterable, Mapping
from uuid import UUID

from app.models import PatchNoteSummary, User


def ensure_user_does_not_exist(
    users: Iterable[User],
    *,
    steam_id: str,
) -> None:
    """A Steam account can be registered once."""
    if any(user.steam_id == steam_id for user in users):
        raise ValueError("A user with the supplied Steam ID already exists.")


def ensure_user_exists(users: Mapping[UUID, User], *, user_id: UUID) -> None:
    """A summary's user_id must name a registered user."""
    if user_id not in users:
        raise LookupError("No user matched the supplied user_id.")


def ensure_summary_is_unique(
    summaries: Iterable[PatchNoteSummary],
    *,
    user_id: UUID,
    game_id: str,
    update_version: str,
    patch_note_id: str | None = None,
) -> None:
    """A user posts at most one summary per game update.

    When both summaries name a patch_note_id, that decides which update they
    are about; update_version is only a label and two patch notes can share
    it. When either summary lacks one, update_version is all there is to go on.
    """

    def same_update(summary: PatchNoteSummary) -> bool:
        if patch_note_id is not None and summary.patch_note_id is not None:
            return summary.patch_note_id == patch_note_id
        return summary.update_version == update_version

    if any(
        summary.user_id == user_id and summary.game_id == game_id and same_update(summary)
        for summary in summaries
    ):
        raise ValueError(
            "A summary for this user, game, and update already exists.",
        )


def find_summary_for_game(
    summaries: Mapping[UUID, PatchNoteSummary],
    *,
    summary_id: UUID,
    game_id: str,
) -> PatchNoteSummary:
    """A summary is found only under the game it was posted for."""
    summary = summaries.get(summary_id)
    if summary is None or summary.game_id != game_id:
        raise LookupError("No patch note summary matched the supplied identifier.")
    return summary
