"""Every (method, path) is registered once (PF12: the OpenAPI export reads
`app.routes`, and a router included twice gives FastAPI's schema duplicate
operation ids)."""

import warnings
from collections import Counter

from fastapi.routing import APIRoute

from app.main import app


def test_no_route_registered_twice():
    seen = Counter(
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or ())
    )
    twice = sorted(f"{method} {path}" for (method, path), n in seen.items() if n > 1)
    assert twice == []


def test_operation_ids_unique():
    app.openapi_schema = None  # build afresh: FastAPI warns on each duplicate
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = app.openapi()
    duplicates = [str(w.message) for w in caught if "Duplicate Operation ID" in str(w.message)]
    assert duplicates == []
    ids = Counter(
        op["operationId"]
        for item in schema["paths"].values()
        for method, op in item.items()
        if isinstance(op, dict) and "operationId" in op
    )
    assert sorted(i for i, n in ids.items() if n > 1) == []
