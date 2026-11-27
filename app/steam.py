"""Client for Steam's store events feed, the source of patch notes.

Steam's documented news API (ISteamNews/GetNewsForApp) has no event type: it
only tags some posts "patchnotes" and cannot tell a hotfix from a season
launch. The store's events feed, the one the Steam client's news page uses,
classifies every post with an event_type and can filter on it:

    12  small update / patch notes (hotfixes, minor patches)
    13  regular update
    14  major update (new seasons, big content patches)

That feed is undocumented, so its shape is checked here: a response that does
not match is reported as Steam being unavailable rather than passed on.
"""

import re
from datetime import UTC, datetime

import httpx
from prometheus_client import Counter
from pydantic import BaseModel, ValidationError

from app.models import SteamPatchNote

EVENTS_URL = "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/"
MAJOR_UPDATE = 14
# The most events the feed returns in one response, whatever count_after asks for.
MAX_EVENTS = 100
TIMEOUT_SECONDS = 10.0

_VERSION = re.compile(r"\b\d+(?:\.\d+)+\b")


# Every call to Steam's events feed, by how it ended. The generic
# http_requests_total shows a 503 from this service; this says whether the
# cause was Steam (unavailable) or a game Steam does not know (not_found), so an
# outage upstream can be told apart from a fault in this service.
STEAM_REQUESTS = Counter(
    "steam_requests_total",
    "Calls to Steam's events feed, by outcome: ok, not_found, unavailable or error.",
    ["outcome"],
)
OUTCOMES = ("ok", "not_found", "unavailable", "error")
for _outcome in OUTCOMES:
    # Start every series at zero, so a query or alert on one finds it before
    # the first failure rather than seeing no data.
    STEAM_REQUESTS.labels(outcome=_outcome)


class SteamUnavailable(Exception):
    """Steam did not answer, or answered with something this client cannot read."""


class GameNotFound(Exception):
    """Steam has no news feed for the requested app ID."""


# --- The parts of Steam's response this client reads ---------------------------


class _AnnouncementBody(BaseModel):
    headline: str
    body: str


class _Event(BaseModel):
    gid: str
    appid: int
    event_name: str
    event_type: int
    rtime32_start_time: int
    hidden: int = 0
    published: int = 1
    announcement_body: _AnnouncementBody | None = None


class _EventsResponse(BaseModel):
    success: int
    events: list[_Event] = []


# --- Client --------------------------------------------------------------------


class SteamClient:
    """Fetches events from Steam. Pass a transport to fake Steam in tests."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def events(self, app_id: str, *, event_type: int) -> list[_Event]:
        """The app's events of one type; every call is counted by its outcome."""
        outcome = "error"
        try:
            found = self._fetch_events(app_id, event_type=event_type)
        except GameNotFound:
            outcome = "not_found"
            raise
        except SteamUnavailable:
            outcome = "unavailable"
            raise
        else:
            outcome = "ok"
            return found
        finally:
            STEAM_REQUESTS.labels(outcome=outcome).inc()

    def _fetch_events(self, app_id: str, *, event_type: int) -> list[_Event]:
        params = {
            "appid": app_id,
            "count_before": 0,
            "count_after": MAX_EVENTS,
            "event_type_filter": event_type,
        }
        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT_SECONDS) as http:
                response = http.get(EVENTS_URL, params=params)
        except httpx.HTTPError as exc:
            raise SteamUnavailable(f"Steam could not be reached: {exc}") from exc

        # Steam answers an app ID it does not know with 400 and
        # {"success": 42, "err_msg": "Failed to determine Official game group ..."}.
        if response.status_code == 400:
            raise GameNotFound(f"Steam has no news feed for app {app_id}.")
        if response.status_code != 200:
            raise SteamUnavailable(f"Steam answered {response.status_code}.")

        try:
            parsed = _EventsResponse.model_validate_json(response.content)
        except ValidationError as exc:
            raise SteamUnavailable("Steam's events feed changed shape.") from exc
        if parsed.success != 1:
            raise SteamUnavailable(f"Steam reported failure code {parsed.success}.")
        return parsed.events

    def major_updates(self, app_id: str) -> list[SteamPatchNote]:
        """The app's major-update announcements, newest first."""
        events = self.events(app_id, event_type=MAJOR_UPDATE)
        return [
            to_patch_note(event)
            for event in events
            # The filter is applied by Steam; checked again in case it is ignored.
            if event.event_type == MAJOR_UPDATE
            and event.published
            and not event.hidden
            and event.announcement_body is not None
        ]


def to_patch_note(event: _Event) -> SteamPatchNote:
    published_at = datetime.fromtimestamp(event.rtime32_start_time, UTC)
    title = event.announcement_body.headline or event.event_name
    return SteamPatchNote(
        patch_note_id=event.gid,
        game_id=str(event.appid),
        text_content=event.announcement_body.body,
        link=f"https://store.steampowered.com/news/app/{event.appid}/view/{event.gid}",
        title=title,
        update_version=update_version(title, published_at),
        published_at=published_at,
    )


def update_version(title: str, published_at: datetime) -> str:
    """Steam has no version field: take one from the title, else use the date.

    "Last Epoch Patch 1.5.4 Notes" gives 1.5.4; "Season 4 is Live Now!" gives
    the publish date, for example 2026.11.04.
    """
    match = _VERSION.search(title)
    return match.group() if match else published_at.strftime("%Y.%m.%d")
