"""Contract enforcement tests."""

from backend.services.contract_enforcer import enforce_contract, analyze_drift


def test_enforce_contract() -> None:
    """Test contract enforcement returns drift analysis with violations."""
    result = enforce_contract(spec_id=1, endpoint_url="http://localhost:8000/api")
    assert isinstance(result, dict)
    assert "drift_score" in result
    assert "violations" in result


def test_analyze_drift() -> None:
    """Test drift analysis returns violation descriptions."""
    result = {"violations": ["missing field", "type mismatch"]}
    violations = analyze_drift(result)
    assert isinstance(violations, list)
    assert len(violations) == 2
