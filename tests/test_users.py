from uuid import UUID


USER = {
    "first_name": "Aidan",
    "last_name": "Rosenboom",
    "steam_id": "76561198012345678",
}


def test_list_users_happy_path(client):
    response = client.get("/v1/users")

    assert response.status_code == 200
    assert response.json() == []


def test_create_user_happy_path(client):
    response = client.post("/v1/users", json=USER)

    body = response.json()
    assert response.status_code == 201
    assert set(body) == {"user_id", "first_name", "last_name", "steam_id"}
    assert UUID(body["user_id"])
    assert body["first_name"] == USER["first_name"]
    assert body["last_name"] == USER["last_name"]
    assert body["steam_id"] == USER["steam_id"]
    assert response.headers["location"].endswith(f"/v1/users/{body['user_id']}")


def test_get_user_happy_path(client):
    created = client.post("/v1/users", json=USER).json()

    response = client.get(f"/v1/users/{created['user_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_create_user_validation_error(client):
    response = client.post("/v1/users", json={"first_name": "Aidan"})

    body = response.json()
    assert response.status_code == 400
    assert body["status"] == 400
    assert body["type"].endswith("/validation-error")
    assert body["errors"]


def test_get_user_not_found_error(client):
    response = client.get("/v1/users/00000000-0000-0000-0000-000000000000")

    body = response.json()
    assert response.status_code == 404
    assert body["status"] == 404
    assert body["type"].endswith("/not-found")


def test_create_user_conflict_error(client):
    client.post("/v1/users", json=USER)

    response = client.post("/v1/users", json=USER)

    body = response.json()
    assert response.status_code == 409
    assert body["status"] == 409
    assert body["type"].endswith("/conflict")
    assert body["conflicts_with"] == {"steam_id": USER["steam_id"]}
