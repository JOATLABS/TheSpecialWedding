"""Tests for the form-template PDF renderer (Phase B).

Covers:
- Every catalog template renders to a valid PDF (magic bytes + non-empty).
- Brand markers appear in the rendered HTML (so the @page margin boxes
  embed correctly).
- Conditional-only fields are still included in the printable PDF —
  the public download is a fillable form, so no fields are hidden.
- LRU cache returns the same bytes on repeat calls and bypasses
  re-render when use_cache=True.
- Unknown template_id raises KeyError.

Source validation: WeasyPrint canonical API confirmed against
https://doc.courtbouillon.org/weasyprint/stable/api_reference.html —
``HTML(string=...).write_pdf()`` returns a ``bytes`` object whose first
4 bytes are the PDF magic ``%PDF``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.services.form_template_catalog import FORM_TEMPLATES  # noqa: E402
from app.services.form_template_pdf_service import (  # noqa: E402
    _render_template_html,
    clear_pdf_cache,
    render_form_template_pdf,
)


# =============================================================================
# HTML render: cheap, no WeasyPrint required
# =============================================================================


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_html_renders_for_every_catalog_template(template):
    """Smoke test: every template builds a valid HTML5 document with
    the title rendered through ``html.escape`` so ``&`` becomes
    ``&amp;``, etc. Catches regressions in the renderer's escape path."""
    import html as _html

    rendered = _render_template_html(template)
    assert rendered.startswith("<!DOCTYPE html>")
    # Title is escaped (matches the renderer's html.escape pass).
    assert _html.escape(template["name"], quote=True) in rendered
    if template.get("description"):
        first_word = template["description"].split()[0]
        assert _html.escape(first_word, quote=True) in rendered


def test_html_includes_branded_margin_boxes():
    """The @page rule must reference the brand strings the marketing
    PDF advertises ("Made with thespecialwedding.io" + "The Special
    Wedding"). Catches accidental brand-string drift."""
    template = FORM_TEMPLATES[0]
    html = _render_template_html(template)
    assert "thespecialwedding.io" in html
    assert "The Special Wedding" in html
    # Page counter in @bottom-right
    assert "counter(page)" in html
    assert "counter(pages)" in html


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_every_field_appears_in_html(template):
    """Conditional fields are still in the printable PDF — guests fill
    by hand. We assert each field's label survives the render.

    Labels go through ``html.escape(quote=True)`` which mangles
    apostrophes / ampersands / quotes / angle brackets. We compare
    against the same escaping so the test stays honest."""
    import html as _html

    rendered = _render_template_html(template)
    for field in template["fields"]:
        label = field.get("label") or ""
        if not label:
            continue
        escaped = _html.escape(label, quote=True)
        assert escaped in rendered, (
            f"template {template['id']} missing field label "
            f"{label!r} in rendered HTML"
        )


def test_html_required_fields_show_required_marker():
    """Required marker is visible so the printed form still tells the
    filler which fields are mandatory."""
    template = FORM_TEMPLATES[0]
    html = _render_template_html(template)
    # At least one required field exists in template[0] (couple_intake)
    assert any(f.get("required") for f in template["fields"])
    assert 'class="required"' in html


def test_html_select_radio_render_options():
    """Choice fields must show their options as bullet items in the PDF."""
    # Use the couple_intake template which has many select / radio fields
    template = next(t for t in FORM_TEMPLATES if t["id"] == "couple_intake")
    html = _render_template_html(template)
    # "Email", "Phone call" etc are options on the communication_preference field
    assert "Email" in html
    assert "Phone call" in html


# =============================================================================
# PDF render: requires WeasyPrint installed
# =============================================================================


_HAS_WEASYPRINT = True
try:
    import weasyprint  # noqa: F401
except Exception:
    _HAS_WEASYPRINT = False


_skip_no_weasyprint = pytest.mark.skipif(
    not _HAS_WEASYPRINT,
    reason="WeasyPrint not installed in this test environment",
)


@_skip_no_weasyprint
@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_pdf_renders_with_valid_magic_bytes_for_every_template(template):
    """End-to-end: every catalog template renders to a valid PDF.

    WeasyPrint returns ``bytes`` starting with the PDF magic ``%PDF``.
    Per the official API reference at
    https://doc.courtbouillon.org/weasyprint/stable/api_reference.html.
    """
    clear_pdf_cache()
    pdf_bytes = render_form_template_pdf(template["id"], use_cache=False)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF"), (
        f"template {template['id']} did not produce a PDF "
        f"(first 16 bytes: {pdf_bytes[:16]!r})"
    )
    # Non-trivial size — at least 1 KB; an empty PDF stub is ~700 bytes.
    assert len(pdf_bytes) > 1024


@_skip_no_weasyprint
def test_cache_returns_same_bytes_on_repeat_call():
    """Phase B's perf optimization: lru_cache hits return the same
    bytes object without re-rendering."""
    clear_pdf_cache()
    template_id = FORM_TEMPLATES[0]["id"]
    first = render_form_template_pdf(template_id)
    second = render_form_template_pdf(template_id)
    # Same Python object identity confirms the cache hit.
    assert first is second


@_skip_no_weasyprint
def test_use_cache_false_bypasses_lru_cache():
    """``use_cache=False`` always re-renders — required for the
    future planner-customised templates path where the same id can
    yield different bytes.

    We can't assert ``first == second`` because WeasyPrint embeds a
    /CreationDate timestamp in the PDF metadata that varies across
    renders. Instead we assert different object identity (proves
    cache was bypassed) and that both produce valid PDFs of similar
    size (proves both renders succeeded)."""
    clear_pdf_cache()
    template_id = FORM_TEMPLATES[0]["id"]
    first = render_form_template_pdf(template_id, use_cache=False)
    second = render_form_template_pdf(template_id, use_cache=False)
    assert first is not second
    assert first.startswith(b"%PDF") and second.startswith(b"%PDF")
    # Sizes are within 5% of each other — guards against an empty
    # render slipping through while tolerating timestamp drift.
    assert abs(len(first) - len(second)) < max(len(first), len(second)) * 0.05


def test_unknown_template_id_raises_key_error():
    with pytest.raises(KeyError):
        render_form_template_pdf("does-not-exist", use_cache=False)


@_skip_no_weasyprint
def test_pdf_size_stays_lean_for_largest_template():
    """Bound the worst-case render so we don't accidentally ship a
    25 MB monstrosity to the public download endpoint. The largest
    catalog template (couple_intake, 17 fields) should comfortably
    render under 200 KB on a single A4 page set."""
    clear_pdf_cache()
    template_id = "couple_intake"
    pdf_bytes = render_form_template_pdf(template_id, use_cache=False)
    assert len(pdf_bytes) < 200 * 1024, (
        f"PDF for {template_id} unexpectedly large: {len(pdf_bytes)} bytes"
    )
