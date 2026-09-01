"""API endpoints for OpenAPI specification management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


specs_router = APIRouter()


class SpecIngest(BaseModel):
    """OpenAPI specification ingestion request."""

    title: str
    version: str
    content: str


class SpecResponse(BaseModel):
    """Stored specification response."""

    id: int
    title: str
    version: str
    uploaded_at: str


@specs_router.post("/specs", response_model=SpecResponse)
def ingest_spec(spec: SpecIngest) -> SpecResponse:
    """Ingest an OpenAPI 3.x specification into the database."""
    from backend.models import Session, Spec
    session = Session()
    spec_record = Spec(
        title=spec.title,
        version=spec.version,
        content=spec.content
    )
    session.add(spec_record)
    session.commit()
    return SpecResponse(
        id=spec_record.id,
        title=spec_record.title,
        version=spec_record.version,
        uploaded_at=str(spec_record.uploaded_at)
    )


@specs_router.get("/specs/{id}", response_model=SpecResponse)
def get_spec(id: int) -> SpecResponse:
    """Retrieve a stored specification by ID."""
    from backend.models import Session, Spec
    session = Session()
    spec_record = session.query(Spec).filter(Spec.id == id).first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="Spec not found")
    return SpecResponse(
        id=spec_record.id,
        title=spec_record.title,
        version=spec_record.version,
        uploaded_at=str(spec_record.uploaded_at)
    )


@specs_router.delete("/specs/{id}")
def delete_spec(id: int) -> dict:
    """Delete a stored specification by ID."""
    from backend.models import Session, Spec
    session = Session()
    spec_record = session.query(Spec).filter(Spec.id == id).first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="Spec not found")
    session.delete(spec_record)
    session.commit()
    return {"deleted": True}