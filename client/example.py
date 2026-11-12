"""Small client example for the deployed Patch Notes API."""

import argparse
from typing import Any

import httpx2 as httpx


def _show_result(label: str, response: httpx.Response) -> None:
    """Print a response in a form useful to a person running the example."""

    print(f"{label}: HTTP {response.status_code}")
    body: Any = response.json()
    if response.is_error:
        print(f"  title: {body.get('title', 'Request failed')}")
        print(f"  detail: {body.get('detail', 'No further details.')}")
        if body.get("errors"):
            print(f"  errors: {body['errors']}")
        if body.get("conflicts_with"):
            print(f"  conflicts_with: {body['conflicts_with']}")
    else:
        print(f"  body: {body}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Patch Notes API example.")
    parser.add_argument(
        "base_url",
        help="API base URL, for example https://se480-aidan-service.onrender.com",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    user_url = f"{base_url}/v1/users"
    payload = {
        "first_name": "Example",
        "last_name": "Client",
        "steam_id": "example-client-76561198000000000",
    }

    print("A sleeping service may take a moment to wake up.")
    try:
        with httpx.Client(timeout=60.0) as client:
            _show_result("List users", client.get(user_url))
            created = client.post(user_url, json=payload)
            _show_result("Create user", created)
            _show_result(
                "Deliberate conflict",
                client.post(user_url, json=payload),
            )
    except httpx.HTTPError as exc:
        print(f"Request failed before the API returned a response: {exc}")


if __name__ == "__main__":
    main()