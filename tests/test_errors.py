"""The error paths that do not come from a route: 405 and the last-resort 500."""

from fastapi.testclient import TestClient
from problems import assert_problem

from app import rules
from app.main import app

USER = {
    "first_name": "Aidan",
    "last_name": "Rosenboom",
    "steam_id": "76561198012345678",
}


def test_unhandled_error_is_a_clean_500(client, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(rules, "ensure_user_does_not_exist", explode)
    # Without raise_server_exceptions=False the RuntimeError would surface in
    # the test instead of the 500 response a real client receives.
    response = TestClient(app, raise_server_exceptions=False).post("/v1/users", json=USER)

    body = assert_problem(response, 500)
    assert body["type"].endswith("/internal-server-error")
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    # The details are not lost: they are in the server log.
    assert "secret internal detail" in caplog.text


def test_wrong_method_lists_every_allowed_method(client):
    response = client.delete("/v1/users")

    body = assert_problem(response, 405)
    assert body["title"] == "Method Not Allowed"
    assert response.headers["allow"] == "GET, POST"


def test_wrong_method_on_item_path(client):
    response = client.put("/v1/patch-note-summaries/6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    assert_problem(response, 405)
    assert response.headers["allow"] == "DELETE, GET"


def test_unknown_path_is_a_problem(client):
    assert_problem(client.get("/v1/nothing-here"), 404)


def test_wrong_method_on_route_outside_the_spec(client):
    response = client.post("/health")

    assert_problem(response, 405)
    assert response.headers["allow"] == "GET"
