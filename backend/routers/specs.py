"""API endpoints for OpenAPI specification management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Spec
from ..services.contract_enforcer import parse_spec

specs_router = APIRouter(prefix="/api", tags=["specs"])


class SpecIngest(BaseModel):
    """OpenAPI specification ingestion request."""

    name: str
    version: str
    content: str


class SpecResponse(BaseModel):
    """Stored specification summary."""

    id: int
    name: str
    version: str
    uploaded_at: str


def _to_response(spec: Spec) -> SpecResponse:
    """Map a Spec row to its API response shape."""
    return SpecResponse(
        id=spec.id,
        name=spec.title,
        version=spec.version,
        uploaded_at=spec.uploaded_at.isoformat(),
    )


def _get_spec_or_404(session: Session, spec_id: int) -> Spec:
    """Fetch a spec by id or raise 404."""
    spec = session.get(Spec, spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec


@specs_router.post("/specs", response_model=SpecResponse, status_code=201)
def ingest_spec(payload: SpecIngest, session: Session = Depends(get_db)) -> SpecResponse:
    """Store an OpenAPI 3.x specification after verifying it parses.

    Args:
        payload: Name, version, and raw spec text (JSON or YAML).
        session: Database session from the dependency.

    Returns:
        The stored spec summary.
    """
    try:
        document = parse_spec(payload.content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"spec does not parse: {error}") from error
    if "paths" not in document:
        raise HTTPException(status_code=400, detail="spec has no paths section")

    spec = Spec(title=payload.name, version=payload.version, content=payload.content)
    session.add(spec)
    session.commit()
    return _to_response(spec)


@specs_router.get("/specs", response_model=list[SpecResponse])
def list_specs(session: Session = Depends(get_db)) -> list[SpecResponse]:
    """Return all stored specs, oldest first."""
    rows = session.query(Spec).order_by(Spec.id).all()
    return [_to_response(row) for row in rows]


@specs_router.get("/specs/{spec_id}", response_model=SpecResponse)
def get_spec(spec_id: int, session: Session = Depends(get_db)) -> SpecResponse:
    """Retrieve a stored specification by id."""
    return _to_response(_get_spec_or_404(session, spec_id))


@specs_router.delete("/specs/{spec_id}")
def delete_spec(spec_id: int, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Delete a stored specification by id."""
    spec = _get_spec_or_404(session, spec_id)
    session.delete(spec)
    session.commit()
    return {"deleted": True}
