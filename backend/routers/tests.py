"""API endpoints for contract enforcement test runs."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Result, Spec, Test
from ..services.contract_enforcer import enforce_contract

tests_router = APIRouter(prefix="/api", tags=["tests"])


class TestRequest(BaseModel):
    """Contract enforcement run request."""

    spec_id: int
    endpoint_url: str
    method: str = "GET"
    path: str


class TestResponse(BaseModel):
    """Test run summary."""

    id: int
    spec_id: int
    endpoint: str
    status: bool
    violations_count: int
    severity_score: float | None


def calculate_severity(violations_count: int) -> float:
    """Score a run by how much it drifted.

    Args:
        violations_count: Number of violations found.

    Returns:
        0.0 for a clean run, rising with the violation count.
    """
    if violations_count == 0:
        return 0.0
    if violations_count <= 2:
        return 1.0
    if violations_count <= 5:
        return 3.0
    return 5.0


@tests_router.post("/tests", response_model=TestResponse, status_code=201)
def run_test(payload: TestRequest, session: Session = Depends(get_db)) -> TestResponse:
    """Run contract enforcement against a live endpoint and store the outcome.

    The endpoint is called with httpx, its JSON body is validated against
    the spec's 200 schema for the given path, and every violation is stored
    as a result row.

    Args:
        payload: Spec id plus the live endpoint to call.
        session: Database session from the dependency.

    Returns:
        The stored run summary with violation count and severity score.
    """
    spec = session.get(Spec, payload.spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Spec not found")

    try:
        violations = enforce_contract(
            spec.content, payload.method, payload.endpoint_url, payload.path
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"endpoint unreachable: {error}") from error

    test = Test(
        spec_id=payload.spec_id,
        endpoint=payload.endpoint_url,
        status=len(violations) == 0,
        severity_score=calculate_severity(len(violations)),
    )
    session.add(test)
    session.flush()
    for violation in violations:
        session.add(
            Result(
                test_id=test.id,
                field_name=violation.field_name,
                expected_type=violation.expected_type,
                actual_type=violation.actual_type,
                breaking_change=violation.breaking_change,
            )
        )
    session.commit()
    return TestResponse(
        id=test.id,
        spec_id=test.spec_id,
        endpoint=test.endpoint,
        status=test.status,
        violations_count=len(violations),
        severity_score=test.severity_score,
    )


@tests_router.get("/tests", response_model=list[TestResponse])
def list_tests(session: Session = Depends(get_db)) -> list[TestResponse]:
    """Return all stored test runs, oldest first."""
    rows = session.query(Test).order_by(Test.id).all()
    return [
        TestResponse(
            id=row.id,
            spec_id=row.spec_id,
            endpoint=row.endpoint,
            status=row.status,
            violations_count=session.query(Result).filter(Result.test_id == row.id).count(),
            severity_score=row.severity_score,
        )
        for row in rows
    ]


@tests_router.get("/tests/{test_id}", response_model=TestResponse)
def get_test(test_id: int, session: Session = Depends(get_db)) -> TestResponse:
    """Retrieve one stored test run by id."""
    row = session.get(Test, test_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return TestResponse(
        id=row.id,
        spec_id=row.spec_id,
        endpoint=row.endpoint,
        status=row.status,
        violations_count=session.query(Result).filter(Result.test_id == row.id).count(),
        severity_score=row.severity_score,
    )
