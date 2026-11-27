import json
from datetime import UTC, datetime

import httpx
import pytest
from problems import assert_problem

from app import steam
from app.main import app
from app.routers.steam_patch_notes import get_steam_client


def _event(**overrides):
    event = {
        "gid": "685265994960078265",
        "appid": 899770,
        "event_name": "Season 4 - Shattered Omens is Live Now!",
        "event_type": 14,
        "rtime32_start_time": 1793898077,
        "hidden": 0,
        "published": 1,
        "announcement_body": {
            "headline": "Last Epoch Patch 1.5.4 Notes",
            "body": "[p]New season, new class.[/p]",
        },
    }
    event.update(overrides)
    return event


@pytest.fixture
def steam_answers(client):
    """Make the fake Steam answer with a status and JSON body; records requests."""
    requests = []

    def answer(status=200, body=None, *, error=None):
        def handler(request):
            requests.append(request)
            if error is not None:
                raise error
            content = body if isinstance(body, bytes) else json.dumps(body).encode()
            return httpx.Response(status, content=content)

        fake = steam.SteamClient(transport=httpx.MockTransport(handler))
        app.dependency_overrides[get_steam_client] = lambda: fake
        return requests

    yield answer


def test_returns_major_updates_from_steam(client, steam_answers):
    requests = steam_answers(body={"success": 1, "events": [_event()]})

    response = client.get("/v1/steam-patch-notes?game_id=899770")

    assert response.status_code == 200
    assert response.json() == [
        {
            "patch_note_id": "685265994960078265",
            "game_id": "899770",
            "text_content": "[p]New season, new class.[/p]",
            "link": "https://store.steampowered.com/news/app/899770/view/685265994960078265",
            "title": "Last Epoch Patch 1.5.4 Notes",
            "update_version": "1.5.4",
            "published_at": "2026-11-05T17:01:17Z",
        }
    ]
    params = requests[0].url.params
    assert params["appid"] == "899770"
    assert params["event_type_filter"] == "14"


def test_drops_events_that_are_not_published_major_updates(client, steam_answers):
    steam_answers(
        body={
            "success": 1,
            "events": [
                _event(event_type=12),
                _event(event_type=13),
                _event(hidden=1),
                _event(published=0),
                _event(announcement_body=None),
                _event(gid="1"),
            ],
        }
    )

    body = client.get("/v1/steam-patch-notes?game_id=899770").json()

    assert [note["link"].rsplit("/", 1)[-1] for note in body] == ["1"]


def test_game_with_no_major_updates_returns_empty_list(client, steam_answers):
    steam_answers(body={"success": 1, "events": []})

    response = client.get("/v1/steam-patch-notes?game_id=10")

    assert response.status_code == 200
    assert response.json() == []


def test_unknown_game_is_not_found(client, steam_answers):
    steam_answers(400, {"success": 42, "err_msg": "Failed to determine Official game group"})

    assert_problem(client.get("/v1/steam-patch-notes?game_id=999999999"), 404)


@pytest.mark.parametrize(
    "status, body, error",
    [
        (503, {}, None),
        (200, b"<html>maintenance</html>", None),
        (200, {"success": 1, "events": [{"gid": "1"}]}, None),
        (200, {"success": 2}, None),
        (200, None, httpx.ConnectTimeout("timed out")),
    ],
    ids=["steam-5xx", "not-json", "changed-shape", "failure-code", "timeout"],
)
def test_steam_problems_are_service_unavailable(client, steam_answers, status, body, error):
    steam_answers(status, body, error=error)

    assert_problem(client.get("/v1/steam-patch-notes?game_id=899770"), 503)


def test_get_steam_patch_notes_validation_error(client):
    response = client.get("/v1/steam-patch-notes")

    body = assert_problem(response, 400)
    assert body["type"].endswith("/validation-error")
    assert body["errors"]


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Last Epoch Hotfix 1.5.2.1 Notes", "1.5.2.1"),
        ("Patch 2.0 is here", "2.0"),
        ("Season 4 - Shattered Omens is Live Now!", "2026.11.05"),
        ("Patch #7 Now Live!", "2026.11.05"),
    ],
)
def test_update_version_comes_from_title_or_date(title, expected):
    published_at = datetime.fromtimestamp(1793898077, UTC)

    assert steam.update_version(title, published_at) == expected
