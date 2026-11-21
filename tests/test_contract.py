from pathlib import Path
from urllib.parse import urlsplit

import pytest
import schemathesis
import yaml
from conftest import no_steam
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

from app.main import app
from app.routers.steam_patch_notes import get_steam_client

SPEC_PATH = Path(__file__).parents[1] / "openapi.yaml"


def _base_path() -> str:
    document = yaml.safe_load(SPEC_PATH.read_text())
    server = document["servers"][0]
    url = server["url"]
    for name, variable in server.get("variables", {}).items():
        url = url.replace("{" + name + "}", variable["default"])
    return urlsplit(url).path.rstrip("/")


BASE_PATH = _base_path()
schema = schemathesis.openapi.from_path(str(SPEC_PATH))
schema.app = app
schema.config.update(base_url="http://testserver" + BASE_PATH)


@pytest.fixture(scope="module", autouse=True)
def _fake_steam():
    # Schemathesis sends many generated game IDs: none of them go to real Steam.
    app.dependency_overrides[get_steam_client] = no_steam
    yield
    app.dependency_overrides.clear()


@schema.parametrize()
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_api_keeps_the_contract(case):
    case.call_and_validate()


def test_openapi_paths_match_application():
    document = yaml.safe_load(SPEC_PATH.read_text())
    expected = {
        (BASE_PATH + path, method.lower())
        for path, path_item in document["paths"].items()
        for method in path_item
        if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}
    }

    response = TestClient(app).get("/openapi.json")
    response.raise_for_status()
    actual = {
        (path, method.lower())
        for path, path_item in response.json()["paths"].items()
        for method in path_item
        if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}
    }

    assert actual == expected
