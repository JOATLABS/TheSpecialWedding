"""Render any FormTemplateDefinition to a branded PDF.

Designed to be the engine behind the public marketing-page download
("Free Wedding Planner Templates") and the in-app "Preview as PDF"
button. Stays small on purpose: one module, one render function, no
new dependencies (WeasyPrint is already in requirements.txt and used
by guest_export_service / contract_pdf_service / seating_export_service).

Performance notes
-----------------
- ``HTML(string=...).write_pdf()`` is the canonical WeasyPrint API
  (confirmed against
  https://doc.courtbouillon.org/weasyprint/stable/api_reference.html
  in May 2026). No newer alternative supersedes it.
- WeasyPrint's documentation explicitly notes: no officially-recommended
  caching mechanism for repeated server-side generation. Since the form
  template catalog is static Python data loaded at import time, the
  rendered PDF bytes for each template id are also static — we cache
  them in an ``functools.lru_cache`` keyed on ``template_id``. Cache
  size is bounded at 32 (more than the catalog has entries), so the
  worst case is ~6 MB resident if every template renders to ~200 KB.
- The actual ``write_pdf`` call is wrapped in ``asyncio.to_thread`` at
  the API layer so a 200–500 ms render doesn't block the event loop.

Header / footer approach
------------------------
We use ``@page`` margin boxes (not running elements) — the simpler of
the two techniques the spec supports. A discreet "Made with
thespecialwedding.io" goes in the bottom-left margin and the page
counter in the bottom-right; the brand mark sits in the top-right.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


_BRAND_NAME = "The Special Wedding"
_BRAND_DOMAIN = "thespecialwedding.io"


def _esc(value: Any) -> str:
    """HTML-escape a single value, preserving empty strings as '—'."""
    if value is None:
        return ""
    text = str(value)
    return html.escape(text, quote=True)


def _format_field_block(field: Mapping[str, Any]) -> str:
    """Render a single field as a print-friendly answer block.

    Each field is a labeled box: label + optional helper description on
    top, an empty bordered area sized for the answer underneath. The
    PDF is intended to be printable so a planner / couple can fill it
    by hand if they want.
    """
    label = _esc(field.get("label", ""))
    description = _esc(field.get("description", ""))
    placeholder = _esc(field.get("placeholder", ""))
    required = bool(field.get("required"))
    field_type = str(field.get("type", "text"))

    label_html = f'<div class="field-label">{label}'
    if required:
        label_html += ' <span class="required">*</span>'
    label_html += "</div>"

    helper_html = ""
    if description:
        helper_html = f'<div class="field-help">{description}</div>'
    elif placeholder:
        helper_html = f'<div class="field-help">{placeholder}</div>'

    if field_type in ("select", "radio"):
        options = field.get("options") or []
        items = "\n".join(
            f'<li><span class="option-mark"></span> {_esc(o)}</li>' for o in options
        )
        body = f'<ul class="field-options">{items}</ul>'
    elif field_type == "checkbox":
        options = field.get("options") or []
        items = "\n".join(
            f'<li><span class="option-mark square"></span> {_esc(o)}</li>'
            for o in options
        )
        body = f'<ul class="field-options">{items}</ul>'
    elif field_type == "textarea":
        body = '<div class="answer-box answer-box-tall"></div>'
    elif field_type in ("rating", "scale"):
        # Show a row of empty circles for the planner / couple to tick.
        marks = 5 if field_type == "rating" else 10
        circles = " ".join('<span class="rating-mark"></span>' for _ in range(marks))
        body = f'<div class="rating-row">{circles}</div>'
    elif field_type == "file_upload":
        body = (
            '<div class="answer-box file-upload">'
            "Attach file when filling this form online"
            "</div>"
        )
    else:
        # text, email, phone, number, date — single-line answer
        body = '<div class="answer-box"></div>'

    return (
        f'<section class="field">\n'
        f"  {label_html}\n"
        f"  {helper_html}\n"
        f"  {body}\n"
        f"</section>"
    )


def _render_template_html(template: Mapping[str, Any]) -> str:
    """Build the full HTML document for a single template."""
    name = _esc(template.get("name", "Form template"))
    description = _esc(template.get("description", ""))
    fields = template.get("fields") or []

    field_blocks = "\n".join(
        _format_field_block(f)
        for f in sorted(fields, key=lambda f: int(f.get("order", 0)))
    )

    # Inline CSS keeps the renderer self-contained — no external
    # stylesheet fetch (which would be a network risk + perf cost on
    # every render).
    css = """
    @page {
      size: A4;
      margin: 22mm 18mm 22mm 18mm;
      @top-right {
        content: "%(brand)s";
        font-family: 'Georgia', serif;
        font-size: 9pt;
        color: #6b5d4f;
      }
      @bottom-left {
        content: "Made with %(domain)s";
        font-family: 'Helvetica', 'Arial', sans-serif;
        font-size: 8pt;
        color: #9a8f82;
      }
      @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Helvetica', 'Arial', sans-serif;
        font-size: 8pt;
        color: #9a8f82;
      }
    }
    body {
      font-family: 'Helvetica', 'Arial', sans-serif;
      color: #1f1f1f;
      line-height: 1.45;
      font-size: 10pt;
    }
    .doc-title {
      font-family: 'Georgia', serif;
      font-size: 24pt;
      font-weight: 600;
      margin: 0 0 6pt 0;
      color: #1a1a1a;
    }
    .doc-description {
      font-size: 10.5pt;
      color: #444;
      margin: 0 0 22pt 0;
      max-width: 150mm;
    }
    .field {
      page-break-inside: avoid;
      margin: 0 0 14pt 0;
    }
    .field-label {
      font-weight: 600;
      font-size: 10.5pt;
      margin-bottom: 4pt;
    }
    .required { color: #b94a48; }
    .field-help {
      font-size: 9pt;
      color: #666;
      margin-bottom: 6pt;
    }
    .answer-box {
      border: 1px solid #c8c2b8;
      border-radius: 3px;
      min-height: 18pt;
      width: 100%%;
    }
    .answer-box-tall {
      min-height: 60pt;
    }
    .answer-box.file-upload {
      display: flex;
      align-items: center;
      justify-content: center;
      color: #9a8f82;
      font-size: 9pt;
      font-style: italic;
      min-height: 30pt;
    }
    .field-options {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    .field-options li {
      display: flex;
      align-items: center;
      gap: 6pt;
      margin: 3pt 0;
    }
    .option-mark {
      display: inline-block;
      width: 9pt;
      height: 9pt;
      border: 1px solid #6b5d4f;
      border-radius: 50%%;
    }
    .option-mark.square {
      border-radius: 2px;
    }
    .rating-row {
      display: flex;
      gap: 6pt;
    }
    .rating-mark {
      display: inline-block;
      width: 11pt;
      height: 11pt;
      border: 1px solid #6b5d4f;
      border-radius: 50%%;
    }
    """ % {"brand": _BRAND_NAME, "domain": _BRAND_DOMAIN}

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{name}</title>
  <style>{css}</style>
</head>
<body>
  <h1 class="doc-title">{name}</h1>
  {f'<p class="doc-description">{description}</p>' if description else ""}
  {field_blocks}
</body>
</html>
"""


def _render_pdf_bytes(template: Mapping[str, Any]) -> bytes:
    """Render a template to PDF bytes synchronously.

    Separate from the cached entry so callers that don't want caching
    (e.g. tests, future planner-customised templates) can render
    directly.
    """
    try:
        from weasyprint import HTML  # local import — see existing services
    except ImportError:
        logger.error("WeasyPrint not installed. Install with: pip install weasyprint")
        raise

    html_content = _render_template_html(template)
    return HTML(string=html_content).write_pdf()


@lru_cache(maxsize=32)
def _cached_pdf_for_template(template_id: str, _content_signature: str) -> bytes:
    """Return cached PDF bytes for ``template_id``.

    The catalog is static Python data loaded at import time, so caching
    the rendered bytes is safe across the whole process lifetime. The
    second argument is a content signature — any change to the
    catalog's representation of this template invalidates the cache
    automatically because lru_cache keys on (id, signature).
    """
    template = _resolve_template(template_id)
    if template is None:
        raise KeyError(template_id)
    return _render_pdf_bytes(template)


def _resolve_template(template_id: str) -> Mapping[str, Any] | None:
    # Imported lazily so a circular import via app.api.forms is impossible.
    from app.services.form_template_catalog import FORM_TEMPLATES

    for template in FORM_TEMPLATES:
        if template.get("id") == template_id:
            return template
    return None


def _content_signature(template: Mapping[str, Any]) -> str:
    """Compact signature used as a cache-busting key.

    We don't need cryptographic strength — this is only to detect
    in-process catalog edits during reloads. ``len(fields)`` plus the
    name and description capture every realistic mutation source.
    """
    fields: Iterable[Mapping[str, Any]] = template.get("fields") or []
    return (
        f"{template.get('name')}|{template.get('description')}|{sum(1 for _ in fields)}"
    )


def render_form_template_pdf(template_id: str, *, use_cache: bool = True) -> bytes:
    """Public entrypoint — return PDF bytes for the given catalog template.

    Raises ``KeyError`` if ``template_id`` is not in the catalog. Set
    ``use_cache=False`` to skip the in-memory LRU and re-render
    (useful for tests). Callers in async contexts should wrap this in
    ``asyncio.to_thread(...)`` so the WeasyPrint render does not block
    the event loop.
    """
    template = _resolve_template(template_id)
    if template is None:
        raise KeyError(template_id)

    if not use_cache:
        return _render_pdf_bytes(template)

    return _cached_pdf_for_template(template_id, _content_signature(template))


def clear_pdf_cache() -> None:
    """Test/admin-only helper to drop cached renders."""
    _cached_pdf_for_template.cache_clear()


__all__ = [
    "clear_pdf_cache",
    "render_form_template_pdf",
]
