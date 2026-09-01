"""Contract enforcement service for API testing."""

from typing import List


class ContractViolation(BaseModel):
    """Schema drift detected between spec and actual endpoint behavior."""

    field_name: str
    expected_type: str
    actual_type: str
    breaking_change: bool


def enforce_contract(spec_content: str, endpoint_response: dict) -> List[ContractViolation]:
    """Enforce contract against live endpoint response. Returns violations when schema drift detected."""
    from jsonschema import validate
    try:
        validate(instance=endpoint_response, schema=spec_content)
        return []
    except Exception as e:
        violations = parse_violations(e, spec_content, endpoint_response)
        return violations


def parse_violations(error: Exception, spec: str, response: dict) -> List[ContractViolation]:
    """Parse JSONSchema validation error into structured contract violations."""
    message = str(error)
    field_name = extract_field(message)
    expected_type = extract_expected(spec, field_name)
    actual_type = extract_actual(response, field_name)
    breaking_change = determine_breaking(expected_type, actual_type)
    return [ContractViolation(
        field_name=field_name,
        expected_type=expected_type,
        actual_type=actual_type,
        breaking_change=breaking_change
    )]


def extract_field(error_message: str) -> str:
    """Extract violated field name from validation error message."""
    if "required" in error_message:
        return error_message.split("required")[1].strip().strip("'")
    return error_message.split("instance")[0].strip()


def extract_expected(spec_content: str, field_name: str) -> str:
    """Extract expected type from OpenAPI spec for given field."""
    if "type" in spec_content and field_name in spec_content:
        return spec_content.split(f'"{field_name}"')[1].split("type")[0].strip()
    return "unknown"


def extract_actual(response_dict: dict, field_name: str) -> str:
    """Extract actual type from endpoint response for given field."""
    if field_name in response_dict:
        value = response_dict[field_name]
        return type(value).__name__
    return "missing"


def determine_breaking(expected_type: str, actual_type: str) -> bool:
    """Determine whether type mismatch constitutes a breaking change."""
    compatible_types = {"string": ["str", "bytes"], "integer": ["int"], "number": ["float"]}
    if expected_type in compatible_types and actual_type in compatible_types[expected_type]:
        return False
    return True