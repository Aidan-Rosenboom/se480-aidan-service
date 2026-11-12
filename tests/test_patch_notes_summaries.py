from uuid import UUID

USER = {
    "first_name": "Aidan",
    "last_name": "Rosenboom",
    "steam_id": "76561198012345678",
}


def create_user(client):
    return client.post("/v1/users", json=USER).json()


def create_summary(client):
    user = create_user(client)
    summary = client.post(
        "/v1/patch-note-summaries",
        json={
            "user_id": user["user_id"],
            "game_id": "10",
            "text_content": "Balance changes",
            "link": "https://example.com/summary",
            "title": "Season update",
            "update_version": "1.4.0",
        },
    )
    return user, summary


def test_list_summaries_happy_path(client):
    response = client.get("/v1/patch-note-summaries?game_id=10")

    assert response.status_code == 200
    assert response.json() == []


def test_create_summary_happy_path(client):
    user = create_user(client)
    response = client.post(
        "/v1/patch-note-summaries",
        json={
            "user_id": user["user_id"],
            "game_id": "10",
            "text_content": "Balance changes",
            "update_version": "1.4.0",
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert set(body) == {
        "user_id",
        "summary_id",
        "game_id",
        "text_content",
        "update_version",
        "created_at",
    }
    assert UUID(body["summary_id"])
    assert UUID(body["user_id"])
    assert body["game_id"] == "10"
    assert body["text_content"] == "Balance changes"
    assert body["update_version"] == "1.4.0"
    assert "link" not in body
    assert "title" not in body
    assert "created_at" in body
    assert response.headers["location"].endswith(
        f"/v1/patch-note-summaries/{body['summary_id']}",
    )


def test_get_summary_happy_path(client):
    _, created = create_summary(client)
    summary_id = created.json()["summary_id"]

    response = client.get(
        f"/v1/patch-note-summaries/{summary_id}?game_id=10",
    )

    assert response.status_code == 200
    assert response.json() == created.json()


def test_delete_summary_happy_path(client):
    _, created = create_summary(client)
    summary_id = created.json()["summary_id"]

    response = client.delete(f"/v1/patch-note-summaries/{summary_id}")

    assert response.status_code == 204
    assert response.content == b""


def test_create_summary_validation_error(client):
    response = client.post(
        "/v1/patch-note-summaries",
        json={"game_id": "10", "text_content": ""},
    )

    body = response.json()
    assert response.status_code == 400
    assert body["status"] == 400
    assert body["type"].endswith("/validation-error")
    assert body["errors"]


def test_create_summary_not_found_error(client):
    response = client.post(
        "/v1/patch-note-summaries",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "game_id": "10",
            "text_content": "Missing user",
            "update_version": "1.0.0",
        },
    )

    body = response.json()
    assert response.status_code == 404
    assert body["status"] == 404
    assert body["type"].endswith("/not-found")


def test_get_summary_not_found_error(client):
    response = client.get(
        "/v1/patch-note-summaries/"
        "00000000-0000-0000-0000-000000000000?game_id=10",
    )

    body = response.json()
    assert response.status_code == 404
    assert body["status"] == 404
    assert body["type"].endswith("/not-found")


def test_delete_summary_not_found_error(client):
    response = client.delete(
        "/v1/patch-note-summaries/"
        "00000000-0000-0000-0000-000000000000",
    )

    body = response.json()
    assert response.status_code == 404
    assert body["status"] == 404
    assert body["type"].endswith("/not-found")


def test_create_summary_conflict_error(client):
    user, first = create_summary(client)
    assert first.status_code == 201

    response = client.post(
        "/v1/patch-note-summaries",
        json={
            "user_id": user["user_id"],
            "game_id": "10",
            "text_content": "Duplicate update",
            "update_version": "1.4.0",
        },
    )

    body = response.json()
    assert response.status_code == 409
    assert body["status"] == 409
    assert body["type"].endswith("/conflict")
    assert body["conflicts_with"] == {
        "user_id": user["user_id"],
        "game_id": "10",
        "update_version": "1.4.0",
    }
