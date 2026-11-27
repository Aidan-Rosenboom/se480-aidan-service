"""Lab 5: the service says what it is doing, and says nothing it should not."""

import json
import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import observability, rules, steam, store
from app.main import app
from app.observability import REQUEST_ID_HEADER, UNMATCHED
from app.routers.steam_patch_notes import get_steam_client

FIELDS = ["ts", "level", "request_id", "method", "route", "status", "duration_ms"]
USER = {
    "first_name": "Aidan",
    "last_name": "Rosenboom",
    "steam_id": "76561198012345678",
}


def logged(capsys) -> list[dict]:
    """Every JSON log line written to standard output since the last call."""
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def counted(route: str, status: str) -> float:
    labels = {"route": route, "status": status}
    return REGISTRY.get_sample_value("http_requests_total", labels) or 0.0


def steam_calls(outcome: str) -> float:
    return REGISTRY.get_sample_value("steam_requests_total", {"outcome": outcome}) or 0.0


def steam_answering(handler) -> None:
    fake = steam.SteamClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_steam_client] = lambda: fake


# --- One line per request -------------------------------------------------------


def test_one_line_per_request_with_its_fields(client, capsys):
    capsys.readouterr()
    response = client.get("/v1/users")
    lines = logged(capsys)
    assert len(lines) == 1
    line = lines[0]
    assert list(line) == FIELDS
    assert (line["level"], line["method"], line["route"], line["status"]) == (
        "INFO",
        "GET",
        "/v1/users",
        200,
    )
    assert line["ts"].endswith("Z")
    assert isinstance(line["duration_ms"], int)
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/v1/users/not-a-uuid", 400),
        ("GET", "/nowhere", 404),
        ("DELETE", "/v1/users", 405),
    ],
)
def test_errors_have_an_id_and_a_line_too(client, capsys, method, path, status):
    capsys.readouterr()
    response = client.request(method, path)
    assert response.status_code == status
    [line] = logged(capsys)
    assert line["status"] == status
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


# --- The route label ------------------------------------------------------------


def test_the_route_is_the_full_template_never_the_path(client, capsys):
    user_id = "00000000-0000-0000-0000-000000000000"
    capsys.readouterr()
    response = client.get(f"/v1/users/{user_id}")
    assert response.status_code == 404
    out = capsys.readouterr().out
    assert user_id not in out
    line = json.loads(out.splitlines()[-1])
    # The /v1 prefix is there: FastAPI 0.165 leaves it off the route's own path.
    assert line["route"] == "/v1/users/{user_id}"


def test_a_path_nobody_defined_gets_one_fixed_label(client, capsys):
    capsys.readouterr()
    client.get("/v1/nothing/here/private-123")
    out = capsys.readouterr().out
    assert "private-123" not in out
    assert json.loads(out.splitlines()[-1])["route"] == UNMATCHED


def test_a_route_outside_the_schema_keeps_its_own_path(client, capsys):
    capsys.readouterr()
    client.get("/")
    assert logged(capsys)[-1]["route"] == "/"


# --- 500s and request ids -------------------------------------------------------


def test_a_500_still_has_its_id_and_its_line(monkeypatch, capsys):
    def explode(*args, **kwargs):
        raise RuntimeError("the store fell over")

    monkeypatch.setattr(rules, "ensure_user_does_not_exist", explode)
    capsys.readouterr()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/v1/users", json=USER)
    assert response.status_code == 500
    # The traceback is written too, after the request line; this is the request line.
    [line] = [line for line in logged(capsys) if "status" in line]
    assert (line["level"], line["status"]) == ("ERROR", 500)
    assert line["route"] == "/v1/users"
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_the_traceback_of_a_500_carries_the_requests_id(monkeypatch, capsys):
    def explode(*args, **kwargs):
        raise RuntimeError("the store fell over")

    monkeypatch.setattr(rules, "ensure_user_does_not_exist", explode)
    capsys.readouterr()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/v1/users", json=USER, headers={REQUEST_ID_HEADER: "trace-500x"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-500x"
    lines = [line for line in logged(capsys) if line["request_id"] == "trace-500x"]
    # One search for the id finds both: the request line and the traceback.
    assert {"status", "exc_info"} <= {key for line in lines for key in line}
    [traceback] = [line for line in lines if "exc_info" in line]
    assert traceback["level"] == "ERROR"
    assert "the store fell over" in traceback["exc_info"]


class _ExplodingStore(dict):
    def __getitem__(self, key):
        raise RuntimeError("the store fell over")


def test_a_500_logs_the_route_and_id_never_the_path(monkeypatch, capsys):
    user_id = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    monkeypatch.setattr(store, "users", _ExplodingStore())
    capsys.readouterr()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/v1/users/{user_id}", headers={REQUEST_ID_HEADER: "trace-500y"})
    out = capsys.readouterr().out
    assert user_id not in out
    traceback = next(json.loads(line) for line in out.splitlines() if '"exc_info"' in line)
    assert traceback["request_id"] == "trace-500y"
    assert (traceback["method"], traceback["route"]) == ("GET", "/v1/users/{user_id}")
    # The caller is asked to quote the id that finds this traceback.
    assert "trace-500y" in response.json()["detail"]


def test_no_body_name_steam_id_or_token_reaches_the_log(client, capsys):
    capsys.readouterr()
    client.post(
        "/v1/users?token=query-secret",
        json=USER,
        headers={"Authorization": "Bearer header-secret"},
    )
    client.post("/v1/users", json=USER)  # the 409, whose problem body names the Steam ID
    out = capsys.readouterr().out
    for secret in (*USER.values(), "query-secret", "header-secret"):
        assert secret not in out


def test_a_steam_warning_carries_the_requests_id(client, capsys):
    steam_answering(lambda request: httpx.Response(502))
    capsys.readouterr()
    response = client.get(
        "/v1/steam-patch-notes?game_id=899770", headers={REQUEST_ID_HEADER: "steam-down-1"}
    )
    assert response.status_code == 503
    warning, request_line = logged(capsys)
    assert (warning["level"], warning["request_id"]) == ("WARNING", "steam-down-1")
    assert "Steam unavailable" in warning["message"]
    assert request_line["request_id"] == "steam-down-1"


def test_logging_is_configured_once():
    before = len(logging.getLogger("app").handlers)
    observability.configure_logging()
    assert len(logging.getLogger("app").handlers) == before


def test_an_incoming_id_is_kept_only_if_it_looks_like_one(client):
    kept = client.get("/v1/users", headers={REQUEST_ID_HEADER: "aidan-test-1"})
    assert kept.headers[REQUEST_ID_HEADER] == "aidan-test-1"
    replaced = client.get("/v1/users", headers={REQUEST_ID_HEADER: 'x","level":"FAKE'})
    assert re.fullmatch(r"[0-9a-f]{16}", replaced.headers[REQUEST_ID_HEADER])


def test_ids_differ_between_requests(client):
    first = client.get("/v1/users").headers[REQUEST_ID_HEADER]
    second = client.get("/v1/users").headers[REQUEST_ID_HEADER]
    assert first != second


# --- /health and /metrics -------------------------------------------------------


def test_health_says_when_it_started_and_what_it_holds(client):
    report = client.get("/health").json()
    assert set(report) == {"status", "started_at", "uptime_seconds", "commit", "store"}
    assert report["status"] == "ok"
    assert report["uptime_seconds"] >= 0
    assert report["store"] == {"users": 0, "summaries": 0}


def test_health_reports_the_deployed_commit_or_unknown(client, monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "fa7c984d0e1b2c3a4f5e6d7c8b9a0f1e2d3c4b5a")
    assert client.get("/health").json()["commit"] == "fa7c984"
    monkeypatch.delenv("RENDER_GIT_COMMIT")
    assert client.get("/health").json()["commit"] == "unknown"


def test_health_counts_what_the_store_holds_never_its_contents(client):
    client.post("/v1/users", json=USER)
    response = client.get("/health")
    assert response.json()["store"] == {"users": 1, "summaries": 0}
    for value in USER.values():
        assert value not in response.text


def test_health_and_metrics_are_not_logged_or_counted(client, capsys):
    capsys.readouterr()
    client.get("/health")
    client.get("/metrics")
    assert logged(capsys) == []
    assert counted("/health", "2xx") == 0.0


def test_a_request_moves_its_counter(client):
    # The registry is shared by the whole process, so assert on the change.
    before = counted("/v1/users", "2xx")
    client.get("/v1/users")
    assert counted("/v1/users", "2xx") == before + 1


def test_metrics_is_served_in_the_prometheus_text_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds_bucket" in response.text
    assert 'steam_requests_total{outcome="unavailable"}' in response.text


def test_a_refused_registration_is_counted(client):
    before = REGISTRY.get_sample_value("steam_id_conflicts_total") or 0.0
    assert client.post("/v1/users", json=USER).status_code == 201
    assert REGISTRY.get_sample_value("steam_id_conflicts_total") == before
    assert client.post("/v1/users", json=USER).status_code == 409
    assert REGISTRY.get_sample_value("steam_id_conflicts_total") == before + 1
    assert "steam_id_conflicts_total" in client.get("/metrics").text


def test_request_metrics_are_labelled_by_route_and_status_class_only(client):
    client.get("/v1/users/6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    checked = set()
    for family in REGISTRY.collect():
        if family.name in ("http_requests", "http_request_duration_seconds"):
            checked.add(family.name)
            for sample in family.samples:
                assert set(sample.labels) - {"le"} <= {"route", "status"}
                assert "6ba7b810" not in sample.labels.get("route", "")
                if "status" in sample.labels:
                    assert re.fullmatch(r"[1-5]xx", sample.labels["status"])
    assert checked == {"http_requests", "http_request_duration_seconds"}


def test_the_startup_switch_refuses_to_start_only_when_set(monkeypatch):
    monkeypatch.delenv("LAB5_FAIL_STARTUP", raising=False)
    observability.fail_startup_if_asked()
    monkeypatch.setenv("LAB5_FAIL_STARTUP", "1")
    with pytest.raises(SystemExit):
        observability.fail_startup_if_asked()


# --- Calls to Steam, by outcome -------------------------------------------------


def test_a_good_answer_from_steam_is_counted_ok(client):
    before = steam_calls("ok")
    assert client.get("/v1/steam-patch-notes?game_id=899770").status_code == 200
    assert steam_calls("ok") == before + 1


def test_a_game_steam_does_not_know_is_counted_not_found(client):
    steam_answering(lambda request: httpx.Response(400, json={"success": 42}))
    before = steam_calls("not_found")
    assert client.get("/v1/steam-patch-notes?game_id=1").status_code == 404
    assert steam_calls("not_found") == before + 1


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(502),
        lambda request: httpx.Response(200, content=b"<html>not json</html>"),
        lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("too slow")),
    ],
    ids=["steam-5xx", "changed-shape", "timeout"],
)
def test_steam_failing_is_counted_unavailable(client, handler):
    steam_answering(handler)
    before = steam_calls("unavailable")
    assert client.get("/v1/steam-patch-notes?game_id=899770").status_code == 503
    assert steam_calls("unavailable") == before + 1


def test_a_bug_in_the_client_is_counted_error_not_unavailable(monkeypatch):
    def explode(self, app_id, *, event_type):
        raise RuntimeError("a bug in this service, not Steam")

    monkeypatch.setattr(steam.SteamClient, "_fetch_events", explode)
    before = steam_calls("error")
    with pytest.raises(RuntimeError):
        steam.SteamClient().events("899770", event_type=steam.MAJOR_UPDATE)
    assert steam_calls("error") == before + 1
