"""
PM Substrate test stub.

This stub exists for the WeddingWebApp Python side to test against.
Real end-to-end (Python ↔ live substrate ↔ Postgres) is P2.3.

The stub is NOT a substrate replica — it is a contract test that verifies:
  1. The Python client sends the right HTTP calls to the right endpoints.
  2. The payload shapes match what the substrate expects.
  3. The architectural invariant holds: budget_category_id does NOT appear
     anywhere in the payment event payload.

The stub runs as an in-process ASGI app via pytest-asyncio's anyio transport,
exposed through an httpx.AsyncClient override. Tests swap out the client's
underlying transport to point at the stub instead of a real substrate.

Usage (in tests):

    from app.integrations.pm_substrate._test_stub import substrate_stub

    async def test_something(substrate_stub):
        client = substrate_stub.build_client()
        pm_id = await client.create_contract(...)
        substrate_stub.assert_event_type("wedding.contract.payment_recorded")

Design:
  - The stub records every POST in order (nodes, edges, events).
  - It returns minimal plausible responses (auto-generated UUIDs for nodes).
  - It enforces no business logic — that belongs in the real substrate.
  - The `assert_no_field_in_events` helper asserts the architectural invariant:
    no field called `budget_category_id` (or similar) appears anywhere in the
    published event payloads.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class SubstrateStub:
    """
    In-memory stub that records all substrate HTTP calls.

    Attributes:
        nodes:   list of node creation bodies (dicts), in call order.
        edges:   list of edge creation bodies (dicts), in call order.
        events:  list of event publication bodies (dicts), in call order.
    """

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear all recorded calls."""
        self.nodes.clear()
        self.edges.clear()
        self.events.clear()

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def assert_event_published(self, event_type: str) -> dict[str, Any]:
        """Assert that at least one event of the given type was published.

        Returns the first matching event body.
        """
        matching = [e for e in self.events if e.get("type") == event_type]
        assert matching, (
            f"Expected at least one event of type {event_type!r} but got: "
            f"{[e.get('type') for e in self.events]}"
        )
        return matching[0]

    def assert_no_field_in_events(self, field_name: str) -> None:
        """Assert that field_name does not appear anywhere in any event payload.

        This is the architectural assertion: `budget_category_id` must NOT appear
        in the `wedding.contract.payment_recorded` payload. The budget rollup
        derives the target from the graph topology, not from the event payload.

        Checks recursively: the field must not appear at top level OR inside
        any nested dict (e.g., inside `payload`).
        """
        for event in self.events:
            _assert_field_absent(event, field_name, context=f"event[type={event.get('type')!r}]")

    def assert_edge_created(self, edge_type: str) -> dict[str, Any]:
        """Assert at least one edge of the given type was created."""
        matching = [e for e in self.edges if e.get("type") == edge_type]
        assert matching, (
            f"Expected edge of type {edge_type!r} but got: "
            f"{[e.get('type') for e in self.edges]}"
        )
        return matching[0]

    def assert_contract_vendor_edge_exists(
        self, pm_contract_id: str, vendor_node_id: str
    ) -> None:
        """Assert the contract_vendor edge was wired correctly."""
        matching = [
            e
            for e in self.edges
            if e.get("type") == "wedding/contract_vendor"
            and e.get("fromId") == pm_contract_id
            and e.get("toId") == vendor_node_id
        ]
        assert matching, (
            f"Expected wedding/contract_vendor edge {pm_contract_id!r} → {vendor_node_id!r}. "
            f"Edges created: {self.edges}"
        )

    def get_payment_events(self) -> list[dict[str, Any]]:
        """Return all payment_recorded events."""
        return [e for e in self.events if e.get("type") == "wedding.contract.payment_recorded"]

    # ------------------------------------------------------------------
    # ASGI app construction
    # ------------------------------------------------------------------

    def _build_app(self) -> Starlette:
        stub = self

        async def create_node(request: Request) -> JSONResponse:
            body = await request.json()
            stub.nodes.append(body)
            # Use caller-supplied id if present, else generate one.
            node_id = body.get("id") or str(uuid.uuid4())
            return JSONResponse(
                {
                    "id": node_id,
                    "tenantId": request.path_params["tenantId"],
                    "profile": body.get("profile", {}),
                    "identity": body.get("identity", {}),
                    "schemaVersion": body.get("schemaVersion", 1),
                }
            )

        async def get_node(request: Request) -> JSONResponse:
            return JSONResponse({"id": request.path_params["id"], "identity": {}})

        async def patch_node(request: Request) -> JSONResponse:
            body = await request.json()
            return JSONResponse({"id": request.path_params["id"], "identity": body.get("identity", {})})

        async def create_edge(request: Request) -> JSONResponse:
            body = await request.json()
            stub.edges.append(body)
            edge_id = str(uuid.uuid4())
            return JSONResponse(
                {
                    "id": edge_id,
                    "type": body.get("type"),
                    "fromId": body.get("fromId"),
                    "toId": body.get("toId"),
                }
            )

        async def delete_edge(request: Request) -> JSONResponse:
            return JSONResponse({"id": request.path_params["edgeId"]})

        async def outgoing_edges(request: Request) -> JSONResponse:
            return JSONResponse({"edges": []})

        async def incoming_edges(request: Request) -> JSONResponse:
            return JSONResponse({"edges": []})

        async def publish_event(request: Request) -> JSONResponse:
            body = await request.json()
            stub.events.append(body)
            event_id = str(uuid.uuid4())
            return JSONResponse(
                {
                    "id": event_id,
                    "type": body.get("type"),
                    "entityId": body.get("entityId"),
                    "tenantId": request.path_params["tenantId"],
                    "payload": body.get("payload", {}),
                }
            )

        async def list_events(request: Request) -> JSONResponse:
            return JSONResponse({"events": []})

        async def healthz(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        routes = [
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            Route("/tenants/{tenantId}/nodes", endpoint=create_node, methods=["POST"]),
            Route("/tenants/{tenantId}/nodes/{nodeId}", endpoint=get_node, methods=["GET"]),
            Route("/tenants/{tenantId}/nodes/{nodeId}", endpoint=patch_node, methods=["PATCH"]),
            Route("/tenants/{tenantId}/edges", endpoint=create_edge, methods=["POST"]),
            Route("/tenants/{tenantId}/edges/{edgeId}", endpoint=delete_edge, methods=["DELETE"]),
            Route(
                "/tenants/{tenantId}/nodes/{nodeId}/edges/out/{type_}",
                endpoint=outgoing_edges,
                methods=["GET"],
            ),
            Route(
                "/tenants/{tenantId}/nodes/{nodeId}/edges/in/{type_}",
                endpoint=incoming_edges,
                methods=["GET"],
            ),
            Route("/tenants/{tenantId}/events", endpoint=publish_event, methods=["POST"]),
            Route("/tenants/{tenantId}/events", endpoint=list_events, methods=["GET"]),
        ]
        return Starlette(routes=routes)

    def build_client(self) -> "PMSubstrateClientStub":
        """Return a PMSubstrateClient backed by this stub's ASGI transport."""
        from app.integrations.pm_substrate.client import PMSubstrateClient

        transport = httpx.ASGITransport(app=self._build_app())
        http_client = httpx.AsyncClient(
            transport=transport,
            base_url="http://stub",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        # Inject the pre-built httpx.AsyncClient so the stub intercepts calls.
        substrate_client = PMSubstrateClient.__new__(PMSubstrateClient)
        substrate_client._base_url = "http://stub"
        substrate_client._timeout = 5.0
        substrate_client._retries = 0
        substrate_client._client = http_client
        return substrate_client  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def substrate_stub() -> SubstrateStub:
    """Pytest fixture: provides a fresh SubstrateStub for each test."""
    return SubstrateStub()


# ---------------------------------------------------------------------------
# Internal assertion helpers
# ---------------------------------------------------------------------------


def _assert_field_absent(obj: Any, field_name: str, context: str) -> None:
    """Recursively assert that field_name does not appear in obj."""
    if isinstance(obj, dict):
        assert field_name not in obj, (
            f"Field {field_name!r} found in {context}: {json.dumps(obj, default=str)[:300]}"
        )
        for key, value in obj.items():
            _assert_field_absent(value, field_name, context=f"{context}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_field_absent(item, field_name, context=f"{context}[{i}]")
