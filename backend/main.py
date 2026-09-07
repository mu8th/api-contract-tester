"""FastAPI entry point for API Contract Tester."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import get_session, init_db
from .models import Spec, Test
from .routers.results import results_router
from .routers.specs import specs_router
from .routers.tests import tests_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize the database when the app starts."""
    init_db()
    yield


app = FastAPI(
    title="API Contract Tester",
    description="Ingest OpenAPI specs and validate live endpoint responses against them.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(specs_router)
app.include_router(tests_router)
app.include_router(results_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Report service status."""
    return {"status": "ok"}


@app.get("/api/contract/dashboard")
async def dashboard_summary() -> dict[str, Any]:
    """Aggregate counts for the dashboard stat cards.

    Returns:
        total_specs, total_runs, total_tests_passed, and health_percentage
        (share of runs with zero violations).
    """
    with get_session() as db:
        total_specs = db.query(Spec).count()
        total_runs = db.query(Test).count()
        passed = db.query(Test).filter(Test.status.is_(True)).count()
    health_percentage = round(passed / total_runs * 100, 1) if total_runs else 100.0
    return {
        "total_specs": total_specs,
        "total_runs": total_runs,
        "total_tests_passed": passed,
        "health_percentage": health_percentage,
    }


# Serve the dashboard after all API routes are registered.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
