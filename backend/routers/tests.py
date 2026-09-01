"""API endpoints for contract enforcement testing."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


tests_router = APIRouter()


class TestRequest(BaseModel):
    """Contract enforcement test request."""

    spec_id: int
    endpoint_url: str
    method: str


class TestResponse(BaseModel):
    """Test execution response."""

    id: int
    spec_id: int
    endpoint: str
    status: bool
    violations_count: int


@tests_router.post("/tests", response_model=TestResponse)
def run_test(test_request: TestRequest) -> TestResponse:
    """Execute contract enforcement test against live endpoint."""
    from backend.models import Session, Test, Spec
    from backend.services.contract_enforcer import enforce_contract
    session = Session()

    spec_record = session.query(Spec).filter(Spec.id == test_request.spec_id).first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="Spec not found")

    violations = enforce_contract(spec_record.content, {"status": 200})
    status = len(violations) == 0
    severity_score = calculate_severity(len(violations))

    test_record = Test(
        spec_id=test_request.spec_id,
        endpoint=test_request.endpoint_url,
        status=status,
        severity_score=severity_score
    )
    session.add(test_record)
    session.commit()
    return TestResponse(
        id=test_record.id,
        spec_id=test_record.spec_id,
        endpoint=test_record.endpoint,
        status=test_record.status,
        violations_count=len(violations)
    )


@tests_router.get("/tests/{id}", response_model=TestResponse)
def get_test(id: int) -> TestResponse:
    """Retrieve test execution record by ID."""
    from backend.models import Session, Test
    session = Session()
    test_record = session.query(Test).filter(Test.id == id).first()
    if not test_record:
        raise HTTPException(status_code=404, detail="Test not found")
    return TestResponse(
        id=test_record.id,
        spec_id=test_record.spec_id,
        endpoint=test_record.endpoint,
        status=test_record.status,
        violations_count=0
    )


def calculate_severity(violations_count: int) -> float:
    """Calculate severity score based on violation count."""
    if violations_count == 0:
        return 0.0
    if violations_count <= 2:
        return 1.0
    if violations_count <= 5:
        return 3.0
    return 5.0