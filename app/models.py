"""Pydantic models for the API request and response shapes.

Every constraint in openapi.yaml's component schemas is declared once here, as
one of the annotated types below, and every model and route parameter that
carries that value uses the type. Rules the schema cannot express live in
app/rules.py.
"""

import re
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    UrlConstraints,
    field_validator,
)

# --- Shared value types (openapi.yaml: components/schemas) -------------------

_UUID_TEXT = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _canonical_uuid(value: Any) -> Any:
    # Pydantic also takes 32 bare hex digits, braces, or a urn: prefix;
    # format: uuid takes only the hyphenated form.
    if isinstance(value, str) and not _UUID_TEXT.fullmatch(value):
        raise ValueError("must be a UUID such as 3fa85f64-5717-4562-b3fc-2c963f66afa6")
    return value


Uuid = Annotated[UUID, BeforeValidator(_canonical_uuid)]

GameId = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,9}$")]
# Steam's gid for an announcement: a 64-bit unsigned integer written as a string.
PatchNoteId = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,19}$")]
SteamId = Annotated[str, StringConstraints(pattern=r"^[0-9]{17}$")]
PersonName = Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"\S")]
SummaryText = Annotated[str, StringConstraints(min_length=1, max_length=10000, pattern=r"\S")]
SummaryTitle = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"\S")]
UpdateVersion = Annotated[
    str,
    StringConstraints(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$"),
]
HttpLink = Annotated[
    AnyUrl,
    UrlConstraints(max_length=2048, allowed_schemes=["http", "https"]),
]


# --- Base models --------------------------------------------------------------


class APIModel(BaseModel):
    """Base model that can be populated from persisted application objects."""

    model_config = ConfigDict(from_attributes=True)


class InputModel(APIModel):
    """A request body: the spec marks these additionalProperties: false."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


# --- Users --------------------------------------------------------------------


class UserFields(APIModel):
    first_name: PersonName = Field(description="User's first name.")
    last_name: PersonName = Field(description="User's last name.")
    steam_id: SteamId = Field(description="Steam identifier associated with the user.")


class UserInput(UserFields, InputModel):
    """Fields required to register a user (RegisterUser)."""


class User(UserFields):
    """A registered user account."""

    user_id: Uuid = Field(description="Unique identifier assigned to the user.")


# Will be implemented in a future API version.
# class SessionInput(InputModel):
#     """Credentials used by the planned session authentication flow."""
#
#     steam_id: SteamId = Field(
#         description="Steam identifier of the user attempting to authenticate.",
#     )
#     password: str = Field(
#         min_length=1,
#         description="Password placeholder for the future authentication flow.",
#     )
#
#
# class Session(APIModel):
#     """Session credentials returned by the planned authentication flow."""
#
#     session_id: Uuid = Field(
#         description="Unique identifier assigned to the session.",
#     )
#     user_id: Uuid = Field(
#         description="Identifier of the authenticated user.",
#     )
#     access_token: str = Field(
#         description="Token reserved for future authenticated operations.",
#     )
#     expires_at: AwareDatetime = Field(
#         description="Time at which the session expires.",
#     )


# --- Patch note summaries -----------------------------------------------------


class PatchNoteSummaryFields(APIModel):
    user_id: Uuid = Field(description="Identifier of the user posting the summary.")
    game_id: GameId = Field(description="Steam application identifier for the game.")
    text_content: SummaryText = Field(description="User-written summary of the patch note.")
    link: HttpLink | None = Field(
        default=None,
        description="Optional URL with additional information about the summary.",
    )
    title: SummaryTitle | None = Field(
        default=None,
        description="Optional title for the summary.",
    )
    update_version: UpdateVersion = Field(description="Version identifier of the game update.")
    patch_note_id: PatchNoteId | None = Field(
        default=None,
        description="Optional patch_note_id of the Steam patch note the summary is about.",
    )

    @field_validator("link", "title", "patch_note_id", mode="before")
    @classmethod
    def _optional_is_not_nullable(cls, value: Any) -> Any:
        # The spec makes these optional (may be left out), not nullable
        # (may be sent as null). Defaults are not validated, so leaving the
        # field out still gives None.
        if value is None:
            raise ValueError("may be left out but not set to null")
        return value


class PatchNoteSummaryInput(PatchNoteSummaryFields, InputModel):
    """Fields supplied when posting a patch note summary."""


class PatchNoteSummary(PatchNoteSummaryFields):
    """A user-posted patch note summary."""

    summary_id: Uuid = Field(description="Unique identifier assigned to the summary.")
    created_at: AwareDatetime = Field(description="Time at which the summary was created.")


# --- Steam patch notes --------------------------------------------------------


class SteamPatchNote(APIModel):
    """A patch note retrieved from Steam."""

    patch_note_id: PatchNoteId = Field(
        description="Steam's identifier for the patch note; stable across edits.",
    )
    game_id: GameId = Field(description="Steam application identifier for the game.")
    text_content: str = Field(description="Patch note content retrieved from Steam.")
    link: HttpLink | None = Field(default=None, description="URL of the patch note on Steam.")
    title: str | None = Field(default=None, description="Optional title of the patch note.")
    update_version: str = Field(description="Version identifier of the game update.")
    published_at: AwareDatetime = Field(
        description="Time at which Steam published the patch note.",
    )
