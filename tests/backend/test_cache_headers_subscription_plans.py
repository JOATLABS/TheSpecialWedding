"""Pin the cache-headers middleware so /subscription-plans never falls into the
public-cacheable branch again.

Background (2026-05-13 admin-save-doesn't-reflect bug forensics):
``app/main.py::add_cache_headers`` middleware classifies every response into
one of six buckets:

  1. Next.js / static-asset paths → long max-age (immutable bundles)
  2. Image / font / css / js extensions → public, max-age=static_cache_max_age
  3. Non-GET methods → no-store (mutations)
  4. Path startswith one of [/api/, /couple-portal/, /couple/, /admin/,
     /vendor-contract/] → no-store
  5. Mutable /subscription-plans and /public/subscription-plans → unconditional no-store
  6. Fallthrough ``else`` → ``public, max-age=300`` (5 minutes)

The ``/subscription-plans`` admin CRUD surface lives at the root path (no
/admin/ prefix because the same router exposes /public/subscription-plans).
Before the fix, that path didn't match any of (1)–(5) and fell into (6).
That gave the browser 5 minutes of public HTTP cache on the admin plan list
GET. After a successful PUT, ``handleSavePlan`` re-fetched the list via
fetch with default cache mode — the browser served the pre-PUT cached body
instead of contacting the server, so the admin UI showed stale state until
a hard reload. See ``app/admin/saas/page.tsx::handleSavePlan``.

This file guards the source-level branch placement. If a future refactor
removes ``path.startswith("/subscription-plans")`` from the no-store list
(or moves it to the public branch), CI fails here before the regression can
ship to production.

Why an AST test, not a TestClient round-trip:
The middleware is registered with @app.middleware("http") on the main app
singleton, which boots a lot of side effects (Mongo, Stripe, Redis) at
import time. The AST approach mirrors ``tests/backend/test_seed_upsert_structure.py``
— it reads the source as text/AST and checks structure without any I/O.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MAIN_PY_PATH = PROJECT_ROOT / "app" / "main.py"


def _load_main_source() -> str:
    return MAIN_PY_PATH.read_text(encoding="utf-8")


def _find_function(
    tree: ast.Module, name: str
) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name == name
        ):
            return node
    raise AssertionError(
        f"{name} not found in app/main.py — has it been renamed? "
        "Update this guard or restore the middleware."
    )


def test_add_cache_headers_middleware_exists():
    """The middleware itself must still exist with its registered name."""
    source = _load_main_source()
    tree = ast.parse(source)
    fn = _find_function(tree, "add_cache_headers")
    assert isinstance(fn, ast.AsyncFunctionDef), (
        "add_cache_headers must remain an async middleware "
        "(it's decorated with @app.middleware('http'))."
    )


def test_subscription_plans_path_in_no_store_branch():
    """``/subscription-plans`` must be classified into the no-store branch.

    Concretely: the source of ``add_cache_headers`` must contain
    ``path.startswith("/subscription-plans")`` AND that call must appear in
    the same elif that already lists /api/, /admin/, etc. — NOT in the
    public-max-age fallthrough.
    """
    source = _load_main_source()
    tree = ast.parse(source)
    fn = _find_function(tree, "add_cache_headers")
    fn_src = ast.unparse(fn)

    assert (
        'path.startswith("/subscription-plans")' in fn_src
        or "path.startswith('/subscription-plans')" in fn_src
    ), (
        "add_cache_headers no longer guards /subscription-plans. Without "
        "this check, GET /subscription-plans?include_inactive=true falls "
        "into the public, max-age=300 fallthrough — see the docstring at "
        'the top of this file. Re-add path.startswith("/subscription-plans") '
        "to the no-store elif in app/main.py."
    )


def test_public_subscription_plans_path_in_no_store_branch():
    """The mutable public catalog must not retain a pre-seed browser response."""
    source = _load_main_source()
    tree = ast.parse(source)
    fn = _find_function(tree, "add_cache_headers")
    fn_src = ast.unparse(fn)

    assert (
        'path.startswith("/public/subscription-plans")' in fn_src
        or "path.startswith('/public/subscription-plans')" in fn_src
    ), (
        "GET /public/subscription-plans still falls into the public five-minute "
        "cache, so the homepage can replace truthful fallback pricing with a "
        "stale plan payload after a canonical seed refresh."
    )


def test_subscription_plans_branch_actually_sets_no_store():
    """Walk the IfNode tree under add_cache_headers and confirm the branch
    containing ``/subscription-plans`` assigns ``no-store`` to Cache-Control,
    not ``public, max-age=...``.

    Defends against the subtler regression where /subscription-plans gets
    moved to the wrong elif (e.g., next to the .css/.js public-cache rule).
    """
    source = _load_main_source()
    tree = ast.parse(source)
    fn = _find_function(tree, "add_cache_headers")

    def _branch_contains_subscription_plans(test_node: ast.expr) -> bool:
        """Return True if the elif test expression mentions /subscription-plans."""
        try:
            test_src = ast.unparse(test_node)
        except Exception:
            return False
        return "/subscription-plans" in test_src

    def _branch_sets_no_store(body: list[ast.stmt]) -> bool:
        """Return True if any statement in this branch's body assigns a
        string containing 'no-store' to Cache-Control."""
        for stmt in body:
            try:
                stmt_src = ast.unparse(stmt)
            except Exception:
                continue
            if "Cache-Control" in stmt_src and "no-store" in stmt_src:
                return True
        return False

    def _collect_branch_statements(body: list[ast.stmt]) -> list[ast.stmt]:
        """Flatten every statement reachable WITHIN the branch body, including
        nested if/elif/else inside it (for the SAFE_GET_CACHE_ENABLED switch).
        Crucially this does NOT cross into sibling branches via ast.walk on
        an enclosing node — it descends only into the body/orelse arms of
        nested If statements rooted at this branch.
        """
        collected: list[ast.stmt] = []
        for stmt in body:
            collected.append(stmt)
            if isinstance(stmt, ast.If):
                collected.extend(_collect_branch_statements(stmt.body))
                collected.extend(_collect_branch_statements(stmt.orelse))
        return collected

    def _find_subscription_plans_branch(
        node: ast.If | None,
    ) -> list[ast.stmt] | None:
        """Walk the if/elif chain and return the body of the elif whose
        test mentions /subscription-plans. Returns None if no match."""
        while node is not None:
            if _branch_contains_subscription_plans(node.test):
                return node.body
            # The orelse of an if/elif chain in CPython is either [] (no
            # else), a single nested If (an elif), or a list of stmts
            # (a terminal else block).
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                node = node.orelse[0]
            else:
                node = None
        return None

    # Locate the top-level if in add_cache_headers (the one inside the
    # ``if settings.enable_cache_headers:`` guard).
    top_level_if: ast.If | None = None
    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.If):
            test_src = ast.unparse(stmt.test)
            if "is_nextjs_asset" in test_src:
                top_level_if = stmt
                break
    assert top_level_if is not None, (
        "Could not locate the cache-decision if/elif chain in "
        "add_cache_headers. Has the middleware been restructured?"
    )

    branch_body = _find_subscription_plans_branch(top_level_if)
    assert branch_body is not None, (
        "No elif branch in add_cache_headers tests for /subscription-plans. "
        'Re-add path.startswith("/subscription-plans") to the no-store '
        "elif in app/main.py — see this file's docstring for why."
    )

    matched_no_store = False
    matched_public = False
    for stmt in _collect_branch_statements(branch_body):
        try:
            stmt_src = ast.unparse(stmt)
        except Exception:
            continue
        if "Cache-Control" not in stmt_src:
            continue
        if "no-store" in stmt_src:
            matched_no_store = True
        if re.search(r"public[^\"']*max-age", stmt_src):
            matched_public = True

    assert matched_no_store, (
        "The elif that handles /subscription-plans does not assign "
        "Cache-Control containing 'no-store'. This is the exact regression "
        "the 2026-05-13 fix in app/main.py prevented — see the docstring "
        "at the top of this file."
    )
    assert not matched_public, (
        "The branch that handles /subscription-plans is now ALSO assigning "
        "Cache-Control: public, max-age=... That re-introduces the bug — "
        "the browser will cache admin plan-list GETs and the admin UI will "
        "go stale after a save until a hard reload."
    )


def test_public_max_age_fallthrough_still_exists_as_else():
    """The catch-all else with ``public, max-age=300`` should still be the
    final branch — we don't want to remove it, only to ensure
    /subscription-plans never falls into it.

    If somebody deletes the else branch entirely, that's a structural
    change worth flagging — alarm here so the author can decide whether
    the new structure is intentional.
    """
    source = _load_main_source()
    assert "public, max-age=300" in source, (
        "The catch-all 'public, max-age=300' branch in add_cache_headers "
        "was removed. That's a structural change. If intentional, update "
        "or delete this test."
    )
