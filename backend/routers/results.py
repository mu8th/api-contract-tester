"""API endpoints for test result and drift details."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Result, Test

results_router = APIRouter(prefix="/api", tags=["results"])


class ViolationDetail(BaseModel):
    """One schema drift finding."""

    id: int
    test_id: int
    field_name: str
    expected_type: str
    actual_type: str
    breaking_change: bool


class TestDriftSummary(BaseModel):
    """Per-test drift summary for the dashboard."""

    test_id: int
    drift_score: float
    violations: list[str]


def _summary_for_test(session: Session, test: Test) -> TestDriftSummary:
    """Build the dashboard summary row for one test run."""
    rows = session.query(Result).filter(Result.test_id == test.id).all()
    fields = [row.field_name for row in rows]
    return TestDriftSummary(
        test_id=test.id,
        drift_score=test.severity_score if test.severity_score is not None else 0.0,
        violations=fields,
    )


@results_router.get("/results", response_model=list[TestDriftSummary])
def get_results(session: Session = Depends(get_db)) -> list[TestDriftSummary]:
    """Return per-test drift summaries, oldest first."""
    tests = session.query(Test).order_by(Test.id).all()
    return [_summary_for_test(session, test) for test in tests]


@results_router.get("/results/{test_id}", response_model=list[ViolationDetail])
def get_results_for_test(test_id: int, session: Session = Depends(get_db)) -> list[ViolationDetail]:
    """Return the detailed violation rows for one test run."""
    if session.get(Test, test_id) is None:
        raise HTTPException(status_code=404, detail="Test not found")
    rows = session.query(Result).filter(Result.test_id == test_id).order_by(Result.id).all()
    return [
        ViolationDetail(
            id=row.id,
            test_id=row.test_id,
            field_name=row.field_name,
            expected_type=row.expected_type,
            actual_type=row.actual_type,
            breaking_change=row.breaking_change,
        )
        for row in rows
    ]
