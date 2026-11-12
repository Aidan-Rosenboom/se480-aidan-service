def test_get_steam_patch_notes_happy_path(client):
    response = client.get("/v1/steam-patch-notes?game_id=10")

    body = response.json()
    assert response.status_code == 200
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["game_id"] == "10"
    assert body[0]["text_content"]
    assert body[0]["link"].startswith("https://")
    assert body[0]["published_at"].endswith("Z")


def test_get_steam_patch_notes_validation_error(client):
    response = client.get("/v1/steam-patch-notes")

    body = response.json()
    assert response.status_code == 400
    assert body["status"] == 400
    assert body["type"].endswith("/validation-error")
    assert body["errors"]
