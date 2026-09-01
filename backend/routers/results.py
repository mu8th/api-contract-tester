"""API endpoints for test result management."""

from typing import List


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


results_router = APIRouter()


class ResultResponse(BaseModel):
    """Test result with schema drift details."""

    id: int
    test_id: int
    field_name: str
    expected_type: str
    actual_type: str
    breaking_change: bool


@results_router.get("/results/{test_id}", response_model=List[ResultResponse])
def get_results(test_id: int) -> List[ResultResponse]:
    """Retrieve test results with schema drift details."""
    from backend.models import Session, Result
    session = Session()

    result_records = session.query(Result).filter(Result.test_id == test_id).all()
    return [ResultResponse(
        id=r.id,
        test_id=r.test_id,
        field_name=r.field_name,
        expected_type=r.expected_type,
        actual_type=r.actual_type,
        breaking_change=r.breaking_change
    ) for r in result_records]


@results_router.get("/results")
def get_all_results() -> List[ResultResponse]:
    """Retrieve all test results."""
    from backend.models import Session, Result
    session = Session()

    result_records = session.query(Result).all()
    return [ResultResponse(
        id=r.id,
        test_id=r.test_id,
        field_name=r.field_name,
        expected_type=r.expected_type,
        actual_type=r.actual_type,
        breaking_change=r.breaking_change
    ) for r in result_records]