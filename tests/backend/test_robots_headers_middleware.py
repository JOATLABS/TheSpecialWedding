"""Pin the X-Robots-Tag middleware so non-public surfaces stay de-indexed.

Background (2026-05-14 GSC "Some fixes failed" forensics):
Google Search Console emailed a "Some fixes failed" notice for
thespecialwedding.io. Root cause: robots.txt Disallow'd routes like
``/admin/``, ``/api/``, ``/setup-account``, ``/reset-password`` so Googlebot
couldn't crawl them, but Disallow alone does not REMOVE pages from the
index — it only blocks future crawling. Anything Google had previously
indexed (or had inbound links for) stayed as "discovered, currently not
indexed" / "crawled, currently not indexed" entries. Re-submitting those
URLs for validation in GSC fails because the bot is robots-blocked and
can't confirm the fix.

Fix (this branch):
  1. ``app/robots.ts`` no longer Disallow's the non-public paths.
  2. ``app/main.py::add_robots_headers`` emits ``X-Robots-Tag: noindex,
     nofollow`` on responses for those paths so Google removes them from
     the index on re-crawl.
  3. ``/admin/login`` is explicitly exempted — it's a public sign-in
     surface and must stay indexable.

This file guards both:
  * The list of de-indexed path prefixes (regressions that drop a
    prefix here would silently re-expose private surfaces to indexing).
  * The exempt list (regressions that drop ``/admin/login`` would
    accidentally de-index the public sign-in page).

Why an AST test, not a TestClient round-trip:
``app/main.py`` boots Mongo / Stripe / Redis at import time, which makes
TestClient assertions expensive and flaky. The pattern here mirrors
``test_cache_headers_subscription_plans.py`` — parse the source as AST
and assert structurally.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MAIN_PY_PATH = PROJECT_ROOT / "app" / "main.py"
ROBOTS_TS_PATH = PROJECT_ROOT / "app" / "robots.ts"


# Path prefixes that MUST remain in the noindex list. Adding a new
# private surface? Append it here AND in app/main.py::_NOINDEX_PATH_PREFIXES.
REQUIRED_NOINDEX_PREFIXES = frozenset(
    {
        "/admin",
        "/api",
        "/otp",
        "/setup-account",
        "/reset-password",
        "/forgot-password",
        "/login",
        "/token",
        "/auth",
        "/couple-portal",
        "/couple/",
        "/vendor-contract",
    }
)

# Path exact-matches that MUST stay indexable even though their prefix
# is in the noindex list above.
REQUIRED_NOINDEX_EXEMPT = frozenset({"/admin/login"})


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


def _find_module_assignment(tree: ast.Module, name: str) -> ast.Assign:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node
    raise AssertionError(
        f"Module-level assignment '{name}' not found in app/main.py. "
        "Either restore it or update this guard."
    )


def _string_collection_from_value(value: ast.expr) -> set[str]:
    """Return the literal string elements of a Tuple/List/Set/Call wrapping
    a tuple/list/set literal (e.g. frozenset((...)))."""
    if isinstance(value, ast.Call):
        # frozenset((...)) — unwrap to the first argument
        if value.args:
            return _string_collection_from_value(value.args[0])
        return set()
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        out: set[str] = set()
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.add(elt.value)
        return out
    return set()


def test_add_robots_headers_middleware_exists():
    """The middleware itself must exist with its registered name."""
    source = _load_main_source()
    tree = ast.parse(source)
    fn = _find_function(tree, "add_robots_headers")
    assert isinstance(fn, ast.AsyncFunctionDef), (
        "add_robots_headers must remain an async middleware "
        "(it's decorated with @app.middleware('http'))."
    )


def test_noindex_path_prefixes_cover_required_surfaces():
    """All known non-public surfaces must be in the noindex list."""
    source = _load_main_source()
    tree = ast.parse(source)
    assignment = _find_module_assignment(tree, "_NOINDEX_PATH_PREFIXES")
    found = _string_collection_from_value(assignment.value)
    missing = REQUIRED_NOINDEX_PREFIXES - found
    assert not missing, (
        f"_NOINDEX_PATH_PREFIXES is missing required entries: {sorted(missing)}. "
        "Removing a prefix here silently re-exposes private surfaces to "
        "Google indexing — see the GSC 'Some fixes failed' forensic trail "
        "in docs/seo/INDEXING.md (2026-05-14)."
    )


def test_noindex_exempt_paths_stay_indexable():
    """The exempt list must still contain the public-by-design paths."""
    source = _load_main_source()
    tree = ast.parse(source)
    assignment = _find_module_assignment(tree, "_NOINDEX_PATH_EXEMPT_EXACT")
    found = _string_collection_from_value(assignment.value)
    missing = REQUIRED_NOINDEX_EXEMPT - found
    assert not missing, (
        f"_NOINDEX_PATH_EXEMPT_EXACT is missing required entries: "
        f"{sorted(missing)}. Removing /admin/login here would accidentally "
        "de-index the public sign-in page."
    )


def test_robots_ts_does_not_disallow_noindexed_paths():
    """robots.txt must not Disallow paths we want Google to re-crawl.

    If a path is in _NOINDEX_PATH_PREFIXES, Googlebot needs to be able
    to fetch it in order to read the X-Robots-Tag: noindex header that
    actually removes it from the index. A robots.txt Disallow blocks
    that read and stalls the de-indexing pipeline.
    """
    robots_source = ROBOTS_TS_PATH.read_text(encoding="utf-8")

    # Crude but durable: look for any 'disallow:' line followed by
    # one of the noindex prefixes. We don't parse TypeScript — we just
    # assert the prefixes never appear as a disallowed string literal.
    for prefix in REQUIRED_NOINDEX_PREFIXES:
        # match e.g. '/admin/', '/api/', '/setup-account'
        # tolerate either trailing slash or not
        candidates = (f"'{prefix}'", f'"{prefix}"', f"'{prefix}/'", f'"{prefix}/"')
        for candidate in candidates:
            # Only fail if the literal appears in the disallow array.
            # The cheapest way to scope: look at the section between
            # the next 'disallow:' and the next ']'.
            idx = robots_source.lower().find("disallow:")
            if idx == -1:
                # No disallow at all — fine.
                break
            section_end = robots_source.find("]", idx)
            section = robots_source[idx:section_end]
            assert candidate not in section, (
                f"robots.txt source disallows {prefix!r}, but that path is "
                "in the X-Robots-Tag noindex list. Disallow blocks Googlebot "
                "from reading the noindex header, so the URL never leaves "
                "the index. Either remove the Disallow OR remove the prefix "
                "from _NOINDEX_PATH_PREFIXES."
            )
