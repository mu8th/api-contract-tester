"""Tests for contract enforcement and the API."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import database
from backend.main import app
from backend.services.contract_enforcer import (
    actual_type_of,
    enforce_contract,
    get_response_schema,
    is_breaking,
    openapi_to_jsonschema,
    parse_spec,
    validate_response,
)

SPEC_JSON = json.dumps(
    {
        "openapi": "3.0.3",
        "info": {"title": "Users API", "version": "1.0.0"},
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "A user",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "name", "active"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "active": {"type": "boolean"},
                    },
                }
            }
        },
    }
)

SPEC_YAML = """
openapi: 3.0.3
info:
  title: Users API
  version: 1.0.0
paths:
  /users/{id}:
    get:
      responses:
        '200':
          description: A user
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
components:
  schemas:
    User:
      type: object
      required: [id, name, active]
      properties:
        id: {type: integer}
        name: {type: string}
        active: {type: boolean}
"""


@pytest.fixture()
def client(tmp_path) -> Iterator[TestClient]:
    """Provide a TestClient backed by a fresh temporary SQLite database."""
    database.init_db(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client


def _free_port() -> int:
    """Find an available localhost port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server() -> Iterator[str]:
    """Run a small real HTTP server whose responses drift from the spec."""
    target = FastAPI()

    @target.get("/users/1")
    def user_ok() -> dict:
        return {"id": 1, "name": "muath", "active": True}

    @target.get("/users/bad")
    def user_bad() -> dict:
        # id is a string and active is missing: two breaking violations.
        return {"id": "one", "name": "drifted"}

    port = _free_port()
    config = uvicorn.Config(target, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/users/1", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        pytest.fail("live test server did not start")

    yield base_url
    server.should_exit = True
    thread.join(timeout=5)


# ── Enforcer unit tests (no network) ────────────────────────────────


def test_parse_spec_json_and_yaml() -> None:
    """Verify both JSON and YAML spec text parse into documents."""
    assert parse_spec(SPEC_JSON)["info"]["title"] == "Users API"
    assert parse_spec(SPEC_YAML)["paths"]["/users/{id}"]["get"] is not None


def test_parse_spec_rejects_garbage() -> None:
    """Verify unparseable spec text raises ValueError."""
    with pytest.raises(ValueError):
        parse_spec("{not json: [")


def test_get_response_schema_resolves_refs() -> None:
    """Verify the 200 schema is extracted and $ref is resolved."""
    schema = get_response_schema(parse_spec(SPEC_JSON), "/users/{id}", "get")
    assert schema is not None
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"id", "name", "active"}
    assert schema["required"] == ["id", "name", "active"]


def test_get_response_schema_missing_operation() -> None:
    """Verify unknown paths and methods return None."""
    spec = parse_spec(SPEC_JSON)
    assert get_response_schema(spec, "/nope", "get") is None
    assert get_response_schema(spec, "/users/{id}", "delete") is None


def test_openapi_to_jsonschema_nested() -> None:
    """Verify nested properties, items, and nullable conversion."""
    schema = {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string", "nullable": True},
        },
    }
    converted = openapi_to_jsonschema(schema, {})
    assert converted["properties"]["tags"]["items"] == {"type": "string"}
    assert converted["properties"]["note"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }


def test_validate_response_passes_on_match() -> None:
    """Verify a conforming body produces no violations."""
    schema = get_response_schema(parse_spec(SPEC_JSON), "/users/{id}", "get")
    assert schema is not None
    violations = validate_response(schema, {"id": 1, "name": "muath", "active": True})
    assert violations == []


def test_validate_response_reports_missing_required_field() -> None:
    """Verify a missing required field is a breaking violation."""
    schema = get_response_schema(parse_spec(SPEC_JSON), "/users/{id}", "get")
    assert schema is not None
    violations = validate_response(schema, {"id": 1, "name": "muath"})
    assert len(violations) == 1
    assert violations[0].field_name == "active"
    assert violations[0].breaking_change is True


def test_validate_response_reports_type_mismatch() -> None:
    """Verify a type mismatch reports expected and actual types."""
    schema = get_response_schema(parse_spec(SPEC_JSON), "/users/{id}", "get")
    assert schema is not None
    violations = validate_response(schema, {"id": "one", "name": "muath", "active": True})
    assert len(violations) == 1
    assert violations[0].field_name == "id"
    assert violations[0].expected_type == "integer"
    assert violations[0].actual_type == "string"
    assert violations[0].breaking_change is True


def test_validate_response_ignores_extra_fields() -> None:
    """Verify extra properties do not violate the contract."""
    schema = get_response_schema(parse_spec(SPEC_JSON), "/users/{id}", "get")
    assert schema is not None
    violations = validate_response(
        schema, {"id": 1, "name": "muath", "active": True, "extra": "ok"}
    )
    assert violations == []


def test_actual_type_of_json_values() -> None:
    """Verify Python values map to JSON type names."""
    assert actual_type_of(None) == "null"
    assert actual_type_of(True) == "boolean"
    assert actual_type_of(1) == "integer"
    assert actual_type_of(1.5) == "number"
    assert actual_type_of("x") == "string"
    assert actual_type_of([]) == "array"
    assert actual_type_of({}) == "object"


def test_is_breaking_only_for_shape_changes() -> None:
    """Verify only required and type errors count as breaking."""
    assert is_breaking("required") is True
    assert is_breaking("type") is True
    assert is_breaking("additionalProperties") is False
    assert is_breaking("enum") is False


# ── API tests (TestClient, temp database) ───────────────────────────


def test_health(client: TestClient) -> None:
    """Verify the health endpoint reports ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_spec_ingest_roundtrip(client: TestClient) -> None:
    """Verify a stored spec is returned by list and get."""
    payload = {"name": "Users API", "version": "1.0.0", "content": SPEC_JSON}
    stored = client.post("/api/specs", json=payload)
    assert stored.status_code == 201
    body = stored.json()
    assert body["name"] == "Users API"
    assert body["uploaded_at"]

    listed = client.get("/api/specs").json()
    assert len(listed) == 1
    fetched = client.get(f"/api/specs/{body['id']}").json()
    assert fetched["id"] == body["id"]

    deleted = client.delete(f"/api/specs/{body['id']}")
    assert deleted.json() == {"deleted": True}
    assert client.get("/api/specs").json() == []


def test_spec_ingest_rejects_invalid_content(client: TestClient) -> None:
    """Verify unparseable or path-less specs are rejected with 400."""
    bad = {"name": "bad", "version": "1", "content": "{not json"}
    assert client.post("/api/specs", json=bad).status_code == 400

    no_paths = {"name": "empty", "version": "1", "content": '{"info": {}}'}
    assert client.post("/api/specs", json=no_paths).status_code == 400


def test_dashboard_summary_counts(client: TestClient) -> None:
    """Verify dashboard aggregates track stored specs and runs."""
    summary = client.get("/api/contract/dashboard").json()
    assert summary["total_specs"] == 0
    assert summary["health_percentage"] == 100.0

    client.post("/api/specs", json={"name": "Users API", "version": "1.0.0", "content": SPEC_JSON})
    summary = client.get("/api/contract/dashboard").json()
    assert summary["total_specs"] == 1


def test_results_grouped_per_test(client: TestClient) -> None:
    """Verify results endpoint returns per-test drift summaries."""
    response = client.get("/api/results")
    assert response.status_code == 200
    assert response.json() == []


# ── Live endpoint enforcement (real HTTP) ───────────────────────────


def test_live_endpoint_passes(client: TestClient, live_server: str) -> None:
    """Verify a conforming live response produces a passing run."""
    spec_id = client.post(
        "/api/specs", json={"name": "Users API", "version": "1.0.0", "content": SPEC_JSON}
    ).json()["id"]

    response = client.post(
        "/api/tests",
        json={
            "spec_id": spec_id,
            "endpoint_url": f"{live_server}/users/1",
            "method": "GET",
            "path": "/users/{id}",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] is True
    assert body["violations_count"] == 0
    assert body["severity_score"] == 0.0

    details = client.get(f"/api/results/{body['id']}").json()
    assert details == []


def test_live_endpoint_reports_drift(client: TestClient, live_server: str) -> None:
    """Verify a drifting live response produces breaking violations."""
    spec_id = client.post(
        "/api/specs", json={"name": "Users API", "version": "1.0.0", "content": SPEC_JSON}
    ).json()["id"]

    response = client.post(
        "/api/tests",
        json={
            "spec_id": spec_id,
            "endpoint_url": f"{live_server}/users/bad",
            "method": "GET",
            "path": "/users/{id}",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] is False
    assert body["violations_count"] == 2

    details = client.get(f"/api/results/{body['id']}").json()
    fields = sorted(v["field_name"] for v in details)
    assert fields == ["active", "id"]
    by_field = {v["field_name"]: v for v in details}
    assert by_field["id"]["expected_type"] == "integer"
    assert by_field["id"]["actual_type"] == "string"
    assert all(v["breaking_change"] for v in details)

    summaries = client.get("/api/results").json()
    assert any(s["test_id"] == body["id"] and len(s["violations"]) == 2 for s in summaries)


def test_enforce_contract_unreachable_endpoint(client: TestClient) -> None:
    """Verify an unreachable endpoint returns 502 without storing a run."""
    spec_id = client.post(
        "/api/specs", json={"name": "Users API", "version": "1.0.0", "content": SPEC_JSON}
    ).json()["id"]

    response = client.post(
        "/api/tests",
        json={
            "spec_id": spec_id,
            "endpoint_url": "http://127.0.0.1:9/unreachable",
            "method": "GET",
            "path": "/users/{id}",
        },
    )
    assert response.status_code == 502


def test_enforce_contract_unknown_path_in_spec(client: TestClient) -> None:
    """Verify a path the spec does not declare is rejected with 400."""
    spec_id = client.post(
        "/api/specs", json={"name": "Users API", "version": "1.0.0", "content": SPEC_JSON}
    ).json()["id"]

    response = client.post(
        "/api/tests",
        json={
            "spec_id": spec_id,
            "endpoint_url": "http://127.0.0.1:9/whatever",
            "method": "GET",
            "path": "/not/in/spec",
        },
    )
    assert response.status_code == 400


def test_enforce_contract_direct_call() -> None:
    """Verify enforce_contract raises ValueError for undeclared operations."""
    with pytest.raises(ValueError):
        enforce_contract(SPEC_JSON, "GET", "http://127.0.0.1:9/x", "/missing")
