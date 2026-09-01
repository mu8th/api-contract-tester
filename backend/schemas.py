"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class SpecCreate(BaseModel):
    """Request to create a new OpenAPI spec."""
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., description="Raw YAML or JSON OpenAPI 3.x spec")
    format: str = Field("yaml", pattern="^(yaml|json)$")


class SpecResponse(BaseModel):
    """Returned spec data."""
    id: int
    name: str
    format: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SpecDetail(SpecResponse):
    """Spec with full content included."""
    content: str


class TestRunCreate(BaseModel):
    """Request to run contract tests against a spec."""
    target_url: str = Field(..., min_length=1)


class TestRunResponse(BaseModel):
    """Test run result summary."""
    id: int
    spec_id: int
    target_url: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    summary_status: Optional[str]

    class Config:
        from_attributes = True


class ContractResultResponse(BaseModel):
    """Individual contract test result."""
    id: int
    spec_id: int
    endpoint_path: Optional[str]
    status: str  # pass | fail | error
    actual_response: Dict[str, Any] = Field(default_factory=dict)
    expected_schema: Optional[str]
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    duration_ms: int
    executed_at: datetime

    class Config:
        from_attributes = True


class DiffReport(BaseModel):
    """Schema drift/violation details."""
    path: str
    expected_type: Optional[str]
    actual_value: Any
    error_type: str  # missing_field | type_mismatch | extra_field | value_change
