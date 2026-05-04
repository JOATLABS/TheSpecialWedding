"""
Typed exceptions for the PM Substrate integration.

Hierarchy:
  PMSubstrateError          — base; any substrate call failure.
    ContractCreationFailed  — substrate rejected a contract node creation.
    PaymentRecordFailed     — substrate rejected a payment_recorded event.
    EdgeCreationFailed      — substrate rejected an edge creation request.
    NodeCreationFailed      — substrate rejected a graph node creation.
"""


class PMSubstrateError(Exception):
    """Base exception for all PM Substrate client failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.args[0]!r}, status_code={self.status_code})"


class ContractCreationFailed(PMSubstrateError):
    """Raised when the substrate rejects a Contract node creation.

    This means the graph write failed — either a validation error from the
    profile-registry or a transient Postgres error. The local MongoDB doc
    should NOT be written if this exception propagates.
    """


class PaymentRecordFailed(PMSubstrateError):
    """Raised when the substrate rejects a wedding.contract.payment_recorded event.

    The budget rollup in @pm/capability-wedding-budget subscribes to this
    event. If the event fails to publish, the rollup will not run — the
    caller should treat this as a hard failure and surface it rather than
    silently recording the local milestone payment without the rollup.
    """


class EdgeCreationFailed(PMSubstrateError):
    """Raised when the substrate rejects an edge creation request.

    For vendor→budgetCategory edges this is fatal: without the edge, the
    budget rollup handler has no path to walk (contract → vendor →
    budgetCategory) and will silently skip the rollup. The caller must
    log and raise — not swallow — so the operator knows the edge is missing.
    """


class NodeCreationFailed(PMSubstrateError):
    """Raised when the substrate rejects a graph node creation.

    Distinct from EdgeCreationFailed so callers can handle node vs. edge
    failures differently. In P2.2 this is surfaced as a hard failure;
    P2.3 will add idempotent upsert semantics backed by a persistent
    node-ID mapping table.
    """
