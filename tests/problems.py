"""Check error responses against the ProblemDetails schema in openapi.yaml.

The schema is read from the spec itself, not from app.errors.ProblemDetails, so
a body the Python model allows but the contract does not still fails here.
"""

from pathlib import Path

import jsonschema_rs
import yaml

_SPEC = yaml.safe_load((Path(__file__).parents[1] / "openapi.yaml").read_text())
_PROBLEM = jsonschema_rs.validator_for(_SPEC["components"]["schemas"]["ProblemDetails"])


def assert_problem(response, status):
    """The response is an RFC 9457 problem with this status, valid per the spec."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    _PROBLEM.validate(body)
    assert body["status"] == status
    return body
