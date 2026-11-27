import httpx
import pytest
from fastapi.testclient import TestClient

from app import steam, store
from app.main import app
from app.routers.steam_patch_notes import get_steam_client


def no_steam() -> steam.SteamClient:
    """A Steam that knows every game and has no major updates for any of them.

    Tests never reach the real Steam; a test that needs other answers overrides
    get_steam_client itself.
    """
    return steam.SteamClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"success": 1, "events": []})
        )
    )


@pytest.fixture
def client():
    store.users.clear()
    store.summaries.clear()
    app.dependency_overrides[get_steam_client] = no_steam
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
