"""Contract enforcement: validate live endpoint responses against OpenAPI schemas.

The enforcer parses an OpenAPI 3.x document, extracts the declared
200-response JSON schema for one operation, calls the live endpoint with
httpx, and reports structured violations when the actual body drifts from
the contract. Missing required fields and type mismatches count as breaking
changes; extra properties and constraint failures do not.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import jsonschema
import yaml
from pydantic import BaseModel


class ContractViolation(BaseModel):
    """One unit of schema drift between spec and live response."""

    field_name: str
    expected_type: str
    actual_type: str
    breaking_change: bool


def parse_spec(content: str) -> dict[str, Any]:
    """Parse an OpenAPI document from JSON or YAML text.

    Args:
        content: Raw spec text.

    Returns:
        Parsed document as a dictionary.

    Raises:
        ValueError: When the text is not a JSON object or YAML mapping.
    """
    try:
        doc = json.loads(content)
    except json.JSONDecodeError:
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as error:
            raise ValueError(f"spec is not valid JSON or YAML: {error}") from error
    if not isinstance(doc, dict):
        raise ValueError("spec must be a JSON object or YAML mapping")
    return doc


def get_response_schema(spec: dict[str, Any], path: str, method: str) -> dict[str, Any] | None:
    """Extract the 200-response JSON schema for one operation.

    Args:
        spec: Parsed OpenAPI document.
        path: Operation path as written in the spec, e.g. /users/{id}.
        method: HTTP method, case-insensitive.

    Returns:
        Converted JSON Schema dict, or None when the operation or its
        application/json 200 schema is not declared.
    """
    paths = spec.get("paths") or {}
    operations = paths.get(path)
    if not isinstance(operations, dict):
        return None
    operation = operations.get(method.lower())
    if not isinstance(operation, dict):
        return None
    responses = operation.get("responses") or {}
    response = responses.get("200")
    if not isinstance(response, dict):
        response = responses.get("default")
    if not isinstance(response, dict):
        return None
    content = response.get("content") or {}
    media = content.get("application/json")
    if not isinstance(media, dict):
        return None
    schema = media.get("schema")
    if not isinstance(schema, dict):
        return None
    return openapi_to_jsonschema(schema, spec)


def openapi_to_jsonschema(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAPI schema node to a JSON Schema.

    Resolves local $ref pointers against the document and keeps the subset
    of keywords jsonschema understands (type, enum, bounds, properties,
    items, required, nullable). Unknown keywords are dropped.

    Args:
        schema: One schema node from the OpenAPI document.
        spec: Full parsed document, used for $ref lookup.

    Returns:
        A JSON Schema dictionary ready for validation.

    Raises:
        ValueError: When a $ref cannot be resolved locally.
    """
    if "$ref" in schema:
        return openapi_to_jsonschema(resolve_ref(schema["$ref"], spec), spec)

    converted: dict[str, Any] = {}
    if isinstance(schema.get("type"), str):
        converted["type"] = schema["type"]
    for key in ("enum", "minimum", "maximum", "minLength", "maxLength", "pattern"):
        if key in schema:
            converted[key] = schema[key]

    properties = schema.get("properties")
    if isinstance(properties, dict):
        converted["properties"] = {
            name: openapi_to_jsonschema(child, spec)
            for name, child in properties.items()
            if isinstance(child, dict)
        }
    items = schema.get("items")
    if isinstance(items, dict):
        converted["items"] = openapi_to_jsonschema(items, spec)
    required = schema.get("required")
    if isinstance(required, list):
        converted["required"] = [str(name) for name in required]

    if schema.get("nullable"):
        converted = {"anyOf": [converted, {"type": "null"}]}
    return converted


def resolve_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local #/... reference against the document.

    Args:
        ref: Reference string, e.g. #/components/schemas/User.
        spec: Full parsed document.

    Returns:
        The referenced schema node.

    Raises:
        ValueError: When the pointer does not resolve to a schema object.
    """
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref pointers are supported, got {ref!r}")
    node: Any = spec
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unresolvable $ref {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref {ref!r} does not point at a schema object")
    return node


def validate_response(schema: dict[str, Any], body: Any) -> list[ContractViolation]:
    """Validate a response body against a JSON Schema.

    Args:
        schema: Converted 200-response schema.
        body: Parsed JSON body from the live endpoint.

    Returns:
        One violation per validation error, sorted by field path.
    """
    validator = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(body), key=lambda e: [str(p) for p in e.path])
    violations: list[ContractViolation] = []
    for error in errors:
        path = list(error.path)
        field_name = ".".join(str(part) for part in path) or "(root)"
        expected_node = _schema_node_at(schema, path)

        # Required errors point at the parent object; attribute them to the
        # specific missing property instead.
        if error.validator == "required" and isinstance(error.instance, dict):
            required = expected_node.get("required", []) if isinstance(expected_node, dict) else []
            missing = [name for name in required if name not in error.instance]
            if missing:
                field_name = ".".join([*map(str, path), missing[0]]) or missing[0]
                if isinstance(expected_node, dict):
                    expected_node = expected_node.get("properties", {}).get(missing[0])

        actual_type = "missing" if error.validator == "required" else actual_type_of(error.instance)
        violations.append(
            ContractViolation(
                field_name=field_name,
                expected_type=_type_name_of_node(expected_node),
                actual_type=actual_type,
                breaking_change=is_breaking(error.validator),
            )
        )
    return violations


def _schema_node_at(schema: dict[str, Any], path: list[Any]) -> dict[str, Any] | None:
    """Walk the schema along a field path and return the node there.

    Args:
        schema: Converted JSON Schema root.
        path: Field path from a validation error.

    Returns:
        The schema node at that position, or None when it cannot be found.
    """
    node: Any = schema
    for part in path:
        if not isinstance(node, dict):
            return None
        properties = node.get("properties")
        items = node.get("items")
        if isinstance(properties, dict) and str(part) in properties:
            node = properties[str(part)]
        elif isinstance(items, dict) and str(part).isdigit():
            node = items
        else:
            return None
    return node if isinstance(node, dict) else None


def _type_name_of_node(node: Any) -> str:
    """Report the declared type name of a schema node.

    Args:
        node: A JSON Schema node, or None.

    Returns:
        The declared type, with anyOf branches joined by "/", or "unknown".
    """
    if not isinstance(node, dict):
        return "unknown"
    any_of = node.get("anyOf")
    if isinstance(any_of, list):
        types = [
            branch["type"]
            for branch in any_of
            if isinstance(branch, dict) and "type" in branch
        ]
        return "/".join(types) or "unknown"
    if "type" in node:
        return str(node["type"])
    return "unknown"


def actual_type_of(value: Any) -> str:
    """Map a Python value to its JSON type name.

    Args:
        value: Parsed JSON value from the response body.

    Returns:
        One of null, boolean, integer, number, string, array, object.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def is_breaking(error_validator: object) -> bool:
    """Decide whether a validation error kind breaks the contract.

    Args:
        error_validator: The jsonschema validator name that failed, e.g.
            "required" or "type". May be a non-string sentinel for errors
            without a named validator.

    Returns:
        True for missing required fields and type mismatches, which change
        the shape consumers rely on. False for everything else.
    """
    return isinstance(error_validator, str) and error_validator in ("required", "type")


def enforce_contract(
    spec_content: str, method: str, endpoint_url: str, path: str
) -> list[ContractViolation]:
    """Call a live endpoint and validate its body against the spec's contract.

    Args:
        spec_content: Raw OpenAPI document text (JSON or YAML).
        method: HTTP method to send, e.g. GET.
        endpoint_url: Full URL of the live endpoint to call.
        path: Operation path as written in the spec, e.g. /users/{id}.

    Returns:
        List of violations; empty when the response honors the contract.

    Raises:
        ValueError: When the spec is unparseable or declares no 200 JSON
            schema for the requested operation.
        httpx.HTTPError: When the endpoint cannot be reached.
    """
    spec = parse_spec(spec_content)
    schema = get_response_schema(spec, path, method)
    if schema is None:
        raise ValueError(f"spec declares no 200 JSON schema for {method.upper()} {path}")

    with httpx.Client(timeout=10.0) as client:
        response = client.request(method.upper(), endpoint_url)

    if response.status_code != 200:
        return [
            ContractViolation(
                field_name="(response)",
                expected_type="HTTP 200",
                actual_type=f"HTTP {response.status_code}",
                breaking_change=True,
            )
        ]
    try:
        body = response.json()
    except ValueError:
        content_type = response.headers.get("content-type", "non-JSON")
        return [
            ContractViolation(
                field_name="(body)",
                expected_type="JSON object",
                actual_type=content_type,
                breaking_change=True,
            )
        ]
    return validate_response(schema, body)
