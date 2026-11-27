"""Lab 5, task 6: the failure that matters, reproduced on demand.

Two requests registering the same Steam account, in flight together. Each one
runs the duplicate check before either user is stored, so each one passes it.
The barrier below is what makes that happen every time: it holds both requests
at the same point, just after the check, and releases them together. The window
is widened here, in the test, and never in the service.

The test is marked as an expected failure, strictly: CI stays green while the
failure stands, and goes red the day the test passes. That day the marker comes
off, and this file becomes the proof that the fix holds.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from app import rules, store
from app.main import app

STEAM_ID = "76561198012345678"
USER = {"first_name": "Aidan", "last_name": "Rosenboom", "steam_id": STEAM_ID}

KNOWN_LIMIT = (
    "Known limit: the duplicate Steam ID check and the write are two steps with nothing "
    "holding the Steam ID between them. Reproduced in Lab 5; the fix is a Week 6 decision."
)


@pytest.mark.xfail(strict=True, reason=KNOWN_LIMIT)
def test_two_requests_in_flight_together_cannot_both_register_one_steam_account(monkeypatch):
    store.users.clear()
    both_have_checked = threading.Barrier(2)
    real_check = rules.ensure_user_does_not_exist

    def check_then_wait(*args, **kwargs):
        real_check(*args, **kwargs)
        try:
            # Wait for the other request to finish its own check. If it never
            # arrives (a fix that lets one request in at a time), stop waiting.
            both_have_checked.wait(timeout=2)
        except threading.BrokenBarrierError:
            pass

    monkeypatch.setattr(rules, "ensure_user_does_not_exist", check_then_wait)
    statuses: list[int] = []

    def register():
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/v1/users", json=USER)
        statuses.append(response.status_code)

    requests = [threading.Thread(target=register) for _ in range(2)]
    for request in requests:
        request.start()
    for request in requests:
        request.join(timeout=10)

    registered = [u for u in store.users.values() if u.steam_id == STEAM_ID]
    store.users.clear()
    # What a correct service does: one 201, one 409, one user.
    assert sorted(statuses) == [201, 409]
    assert len(registered) == 1
