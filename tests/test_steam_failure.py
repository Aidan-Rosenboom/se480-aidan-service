"""Lab 5, task 6: the failure that matters, reproduced on demand.

The proposal names GET /v1/steam-patch-notes as the highest-risk operation:
Steam can answer with the wrong game, stale or malformed data, or not at all.
Not at all is handled: a 503, a warning in the log, and
steam_requests_total{outcome="unavailable"} moves. The wrong game is not. Steam
answers 200, every field has the right shape, and the client passes the posts
on as they came, so a player who asked for Last Epoch is shown Dota 2's patch
notes, the log says INFO, and the counters call it ok.

The test is marked as an expected failure, strictly: CI stays green while the
failure stands, and goes red the day the test passes. That day the marker comes
off, and this file becomes the proof that the fix holds.
scripts/reproduce_steam_failure.py shows the same thing against a running
service, with every signal.
"""

import httpx
import pytest

from app import steam
from app.main import app
from app.routers.steam_patch_notes import get_steam_client

KNOWN_LIMIT = (
    "Known limit: the Steam client never checks that the events Steam returns are for "
    "the game it asked about. Reproduced in Lab 5; not fixed in this task."
)


def _steam_answers_with_dota(request: httpx.Request) -> httpx.Response:
    event = {
        "gid": "5700001",
        "appid": 570,
        "event_name": "Dota 2 Gameplay Update 7.40",
        "event_type": 14,
        "rtime32_start_time": 1793898077,
        "announcement_body": {"headline": "Dota 2 Gameplay Update 7.40", "body": "[p]x[/p]"},
    }
    return httpx.Response(200, json={"success": 1, "events": [event]})


@pytest.mark.xfail(strict=True, reason=KNOWN_LIMIT)
def test_patch_notes_are_only_ever_for_the_game_asked_about(client):
    fake = steam.SteamClient(transport=httpx.MockTransport(_steam_answers_with_dota))
    app.dependency_overrides[get_steam_client] = lambda: fake

    response = client.get("/v1/steam-patch-notes?game_id=899770")

    # What a correct service does: never another game's notes. An empty list or
    # a 503 would both be honest; Dota 2's notes under Last Epoch are not.
    assert all(note["game_id"] == "899770" for note in response.json())
