"""Tests for the new endpoint GET /ict/sessions/{id}/papel-trabajo.

Verifies routing wiring: the endpoint exists, requires auth (it returns
something that doesn't crash the FastAPI router at import time).
For end-to-end behavior with a real session, see Task PT-12
(scripts/verify_papel_trabajo_prophar.py).
"""
import inspect

from backend.app.ict import router as ict_router


def test_papel_trabajo_route_is_registered():
    """The new route GET /sessions/{session_id}/papel-trabajo must be
    declared in the router. This guards against accidental deletion."""
    routes = ict_router.router.routes
    matching = [
        r for r in routes
        if hasattr(r, "path") and "papel-trabajo" in r.path
    ]
    assert len(matching) == 1, (
        f"Expected exactly 1 papel-trabajo route, found {len(matching)}"
    )
    route = matching[0]
    assert "GET" in route.methods, (
        f"Route should be GET, got methods: {route.methods}"
    )


def test_papel_trabajo_handler_has_session_id_param():
    """The handler signature must accept session_id as a path parameter."""
    from backend.app.ict.router import download_papel_trabajo_endpoint
    sig = inspect.signature(download_papel_trabajo_endpoint)
    assert "session_id" in sig.parameters
    # Type should be int (FastAPI standard).
    # Due to `from __future__ import annotations`, the annotation may be
    # the string "int" rather than the class itself.
    param = sig.parameters["session_id"]
    assert param.annotation in (int, "int"), (
        f"session_id should be int, got {param.annotation!r}"
    )


def test_sri_and_papel_trabajo_routes_coexist():
    """Both /download (SRI) and /papel-trabajo must exist in parallel."""
    routes = ict_router.router.routes
    paths = {r.path for r in routes if hasattr(r, "path")}
    has_sri = any("/sessions/{session_id}/download" in p for p in paths)
    has_papel = any("/sessions/{session_id}/papel-trabajo" in p for p in paths)
    assert has_sri, "Endpoint SRI /download faltante"
    assert has_papel, "Endpoint papel-trabajo faltante"
