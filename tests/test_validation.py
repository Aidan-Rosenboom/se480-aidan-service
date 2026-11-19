"""Every constraint in openapi.yaml is enforced, not only the ones the
contract test happens to generate. One case per constraint."""

import pytest
from problems import assert_problem

from app import rules

USER = {
    "first_name": "Aidan",
    "last_name": "Rosenboom",
    "steam_id": "76561198012345678",
}


def summary_body(owner, **changes):
    body = {
        "user_id": owner,
        "game_id": "10",
        "text_content": "Balance changes",
        "update_version": "1.4.0",
    }
    body.update(changes)
    return {k: v for k, v in body.items() if v is not ...}


@pytest.fixture
def user_id(client):
    return client.post("/v1/users", json=USER).json()["user_id"]


def assert_rejected(response, field):
    assert_problem(response, 400)
    body = response.json()
    assert body["type"].endswith("/validation-error")
    assert field in {error["field"] for error in body["errors"]}


# --- RegisterUser ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_name", ""),
        ("first_name", "   "),
        ("first_name", "a" * 101),
        ("last_name", ""),
        ("last_name", "b" * 101),
        ("steam_id", ""),
        ("steam_id", "7656119801234567"),  # 16 digits
        ("steam_id", "765611980123456789"),  # 18 digits
        ("steam_id", "7656119801234567x"),
        ("steam_id", 76561198012345678),  # a number, not a string
        ("first_name", None),
    ],
)
def test_register_user_rejects_bad_field(client, field, value):
    response = client.post("/v1/users", json={**USER, field: value})
    assert_rejected(response, field)


def test_register_user_accepts_limits(client):
    body = {**USER, "first_name": "a" * 100, "last_name": "b"}
    assert client.post("/v1/users", json=body).status_code == 201


def test_register_user_rejects_unknown_field(client):
    response = client.post("/v1/users", json={**USER, "user_id": "x", "admin": True})
    assert_rejected(response, "admin")
    assert_rejected(response, "user_id")


def test_user_path_requires_hyphenated_uuid(client):
    response = client.get("/v1/users/3fa85f6457174562b3fc2c963f66afa6")
    assert_rejected(response, "user_id")


# --- PatchNoteSummaryInput ---------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("game_id", ""),
        ("game_id", "0"),
        ("game_id", "010"),
        ("game_id", "-5"),
        ("game_id", "12345678901"),  # 11 digits
        ("game_id", "abc"),
        ("text_content", ""),
        ("text_content", " \n\t"),
        ("text_content", "x" * 10001),
        ("title", ""),
        ("title", "t" * 201),
        ("title", None),
        ("update_version", ""),
        ("update_version", ".1"),
        ("update_version", "1.0 beta"),
        ("update_version", "v" * 51),
        ("link", "ftp://example.com/file"),
        ("link", "example.com/no-scheme"),
        ("link", "https://example.com/" + "a" * 2048),
        ("link", None),
        ("user_id", "not-a-uuid"),
        ("user_id", ...),  # missing
        ("update_version", ...),
    ],
)
def test_create_summary_rejects_bad_field(client, user_id, field, value):
    response = client.post("/v1/patch-note-summaries", json=summary_body(user_id, **{field: value}))
    assert_rejected(response, field)


def test_create_summary_accepts_limits(client, user_id):
    body = summary_body(
        user_id,
        game_id="4294967295",
        text_content="x" * 10000,
        title="t" * 200,
        update_version="v1.4.0-beta+build_7",
        link="http://example.com/notes",
    )
    response = client.post("/v1/patch-note-summaries", json=body)
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("field", ["summary_id", "created_at", "author"])
def test_create_summary_rejects_unknown_or_server_fields(client, user_id, field):
    body = summary_body(user_id, **{field: "2026-11-04T04:00:00Z"})
    assert_rejected(client.post("/v1/patch-note-summaries", json=body), field)


@pytest.mark.parametrize("path", ["/v1/patch-note-summaries", "/v1/steam-patch-notes"])
@pytest.mark.parametrize("game_id", ["", "0", "abc", "null"])
def test_game_id_query_is_a_positive_integer(client, path, game_id):
    assert_rejected(client.get(path, params={"game_id": game_id}), "game_id")


def test_summary_item_query_game_id_is_validated(client):
    response = client.get(
        "/v1/patch-note-summaries/6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        params={"game_id": "abc"},
    )
    assert_rejected(response, "game_id")


def test_created_at_carries_an_offset(client, user_id):
    body = client.post("/v1/patch-note-summaries", json=summary_body(user_id)).json()
    assert body["created_at"].endswith(("Z", "+00:00"))


# --- Rules (app/rules.py) -----------------------------------------------------


def test_summary_is_only_found_under_its_game(client, user_id):
    created = client.post("/v1/patch-note-summaries", json=summary_body(user_id)).json()
    response = client.get(
        f"/v1/patch-note-summaries/{created['summary_id']}", params={"game_id": "20"}
    )
    assert_problem(response, 404)


def test_same_update_for_another_game_is_not_a_conflict(client, user_id):
    assert client.post("/v1/patch-note-summaries", json=summary_body(user_id)).status_code == 201
    other_game = summary_body(user_id, game_id="20")
    assert client.post("/v1/patch-note-summaries", json=other_game).status_code == 201


def test_ensure_user_exists_raises_lookup_error():
    from uuid import uuid4

    with pytest.raises(LookupError):
        rules.ensure_user_exists({}, user_id=uuid4())


def test_find_summary_for_game_raises_lookup_error():
    from uuid import uuid4

    with pytest.raises(LookupError):
        rules.find_summary_for_game({}, summary_id=uuid4(), game_id="10")
