"""FastAPI entry point for API Contract Tester."""

from fastapi import FastAPI
from backend.routers.specs import specs_router
from backend.routers.tests import tests_router
from backend.routers.results import results_router


app = FastAPI(
    title="API Contract Tester",
    description="Self-hosted platform that ingests OpenAPI specifications and maintains living contracts between code and expected behavior."
)

app.include_router(specs_router)
app.include_router(tests_router)
app.include_router(results_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)