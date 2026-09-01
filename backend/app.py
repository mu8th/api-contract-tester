"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import router as contract_router

app = FastAPI(
    title="Contract Test",
    description="A self-hosted platform for maintaining living API contracts between your code and expected behavior.",
    version="0.1.0",
)

# CORS middleware (allow local dev frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(contract_router)


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Root endpoint — redirects to dashboard or serves docs."""
    return {"message": "Contract Test running", "docs": "/docs"}
