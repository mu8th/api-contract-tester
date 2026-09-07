"""API routers for API Contract Tester."""

from .results import results_router
from .specs import specs_router
from .tests import tests_router

__all__ = ["results_router", "specs_router", "tests_router"]
