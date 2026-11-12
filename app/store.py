"""In-memory data access used by the API while the service is running."""

from uuid import UUID

from app.models import PatchNoteSummary, User

users: dict[UUID, User] = {}
summaries: dict[UUID, PatchNoteSummary] = {}