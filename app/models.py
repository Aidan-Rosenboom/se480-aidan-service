"""Pydantic models for the API request and response shapes."""

from uuid import UUID

from pydantic import AwareDatetime, AnyUrl, BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base model that can be populated from persisted application objects."""

    model_config = ConfigDict(from_attributes=True)


class UserInput(APIModel):
    """Fields required to register a user."""

    first_name: str = Field(
        description="User's first name."
    )
    
    last_name: str = Field(
        description="User's last name."
        )
    
    steam_id: str = Field(
        description="Steam identifier associated with the user.",
    )




class User(UserInput):
    """A registered user account."""

    user_id: UUID = Field(
        description="Unique identifier assigned to the user.",
    )
    
    first_name: str = Field(
        description="User's first name.",
        alias="first_name"
    )

    last_name: str = Field(
        description="User's last name.",
        alias="last_name"
    )

    steam_id: str = Field(
        description="Steam identifier associated with the user.",
    )

# Will be implemented in a future API version.
# class SessionInput(APIModel):
#     """Credentials used by the planned session authentication flow."""
#
#     steam_id: str = Field(
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
#     session_id: UUID = Field(
#         description="Unique identifier assigned to the session.",
#     )
#     user_id: UUID = Field(
#         description="Identifier of the authenticated user.",
#     )
#     access_token: str = Field(
#         description="Token reserved for future authenticated operations.",
#     )
#     expires_at: AwareDatetime = Field(
#         description="Time at which the session expires.",
#     )



class PatchNoteSummaryInput(APIModel):
    """Fields supplied when posting a patch note summary."""
    
    user_id: UUID = Field(
        description="Identifier of the user posting the summary.",
    )

    game_id: str = Field(
        description="Steam application identifier for the game.",
    )

    text_content: str = Field(
        min_length=1,
        description="User-written summary of the patch note.",
    )

    link: AnyUrl | None = Field(
        default=None,
        description="Optional URL with additional information about the summary.",
    )

    title: str | None = Field(
        default=None,
        description="Optional title for the summary.",
    )

    update_version: str = Field(
        min_length=1,
        description="Version identifier of the game update.",
    )

class PatchNoteSummary(PatchNoteSummaryInput):
    """A user-posted patch note summary."""

    user_id: UUID = Field(
        description="Identifier of the user posting the summary.",
    )

    summary_id: UUID = Field(
        description="Unique identifier assigned to the summary.",
    )

    game_id: str = Field(
        description="Steam application identifier for the game.",
    )
    
    text_content: str = Field(
        min_length=1,
        description="User-written summary of the patch note.",
    )

    link: AnyUrl | None = Field(
        default=None,
        description="Optional URL with additional information about the summary.",
    )

    title: str | None = Field(
        default=None,
        description="Optional title for the summary.",
    )

    update_version: str = Field(
        min_length=1,
        description="Version identifier of the game update.",
    )

    created_at: AwareDatetime = Field(
        description="Time at which the summary was created.",
    )


class SteamPatchNote(APIModel):
    """A patch note retrieved from Steam."""

    game_id: str = Field(
        description="Steam application identifier for the game.",
    )

    text_content: str = Field(
        description="Patch note content retrieved from Steam.",
    )

    link: AnyUrl | None = Field(
        default=None,
        description="URL of the patch note on Steam.",
    )

    title: str | None = Field(
        default=None,
        description="Optional title of the patch note.",
    )

    update_version: str = Field(
        description="Version identifier of the game update.",
    )

    published_at: AwareDatetime = Field(
        description="Time at which Steam published the patch note.",
    )
