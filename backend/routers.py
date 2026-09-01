"""FastAPI router for API contract testing endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Spec, ContractResult, TestRun
from backend.schemas import (
    SpecCreate,
    SpecResponse,
    SpecDetail,
    TestRunCreate,
    TestRunResponse,
    ContractResultResponse,
)

router = APIRouter(prefix="/api/contract", tags=["Contract Testing"])


# ────────────────────────────────
# Specs CRUD
# ────────────────────────────────

@router.post("/specs")
def create_spec(spec: SpecCreate, db: Session = Depends(get_db)):
    """Create a new OpenAPI spec for contract testing."""
    new_spec = Spec(name=spec.name, content=spec.content, format=spec.format)
    db.add(new_spec)
    db.commit()
    db.refresh(new_spec)
    return {"id": new_spec.id, "name": new_spec.name}


@router.get("/specs/{spec_id}")
def get_spec(spec_id: int, detail: bool = False, db: Session = Depends(get_db)):
    """Get a spec by ID. Use ?detail=true to include full content."""
    spec = db.query(Spec).filter(Spec.id == spec_id).first()
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    result = SpecResponse(
        id=spec.id,
        name=spec.name,
        format=spec.format,
        created_at=spec.created_at,
        updated_at=spec.updated_at,
    )

    if detail:
        return {**result.model_dump(), "content": spec.content}
    return result


@router.get("/specs")
def list_specs(limit: int = 50, db: Session = Depends(get_db)):
    """List all specs with optional limit."""
    specs = db.query(Spec).order_by(Spec.updated_at.desc()).limit(limit).all()
    return [SpecResponse.model_validate(s) for s in specs]


# ────────────────────────────────
# Test Runs
# ────────────────────────────────

@router.post("/runs")
def create_test_run(run: TestRunCreate, db: Session = Depends(get_db)):
    """Start a new contract test run against all paths in an OpenAPI spec."""
    # Create the test run record first (so we can track results)
    new_run = TestRun(
        spec_id=run.spec_id,
        target_url=run.target_url,
        started_at=None,  # Will be set by actual execution logic later
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    return {"id": new_run.id, "status": "started"}


@router.get("/runs/{run_id}")
def get_test_run(run_id: int, db: Session = Depends(get_db)):
    """Get a test run result."""
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return TestRunResponse.model_validate(run)


# ────────────────────────────────
# Contract Results
# ────────────────────────────────

@router.get("/results/{run_id}")
def get_contract_results(run_id: int, db: Session = Depends(get_db)):
    """Get all contract test results for a specific run."""
    results = (
        db.query(ContractResult)
        .filter(ContractResult.id == run_id)
        .order_by(ContractResult.executed_at.desc())
        .all()
    )
    return [ContractResultResponse.model_validate(r) for r in results]


# ────────────────────────────────
# Dashboard Summary
# ────────────────────────────────

@router.get("/dashboard")
def dashboard_stats(db: Session = Depends(get_db)):
    """Aggregate stats for the live dashboard."""
    total_specs = db.query(Spec).count()
    total_runs = db.query(TestRun).count()
    
    # Count results by status
    pass_count = (
        db.query(ContractResult)
        .filter(ContractResult.status == "pass")
        .count()
    )
    fail_count = (
        db.query(ContractResult)
        .filter(ContractResult.status == "fail")
        .count()
    )

    return {
        "total_specs": total_specs,
        "total_runs": total_runs,
        "total_tests_passed": pass_count,
        "total_tests_failed": fail_count,
        "health_percentage": round(
            (pass_count / max(pass_count + fail_count, 1)) * 100, 2
        ),
    }
