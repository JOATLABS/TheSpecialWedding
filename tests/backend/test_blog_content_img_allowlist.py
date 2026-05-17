"""
Tests for the <img> allowlist in app/utils/blog_content.py.

Covers two layers of defense:
  1. Bleach allowlist — only `src`, `alt`, `width`, `height`, `loading`
     attributes survive. `onerror`, `srcset`, `style`, etc. are dropped.
  2. Post-bleach _enforce_https_image_src pass — drops <img> tags whose
     src is not an https:// URL. Rejects http:, data:, javascript:,
     blob:, file:, relative paths, and missing src.

Also includes regression coverage for existing non-img sanitization
to make sure adding `img` to BLOG_ALLOWED_TAGS / EDITORIAL_HTML_PATTERN
didn't break any prior behavior.
"""

from app.utils.blog_content import sanitize_blog_content


# ─────────────────────────────── HTTPS survives ───────────────────────────────


def test_https_img_survives_intact():
    content = '<p>Body</p><img src="https://cdn.example.com/x.jpg" alt="A photo">'
    sanitized = sanitize_blog_content(content)

    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized
    assert 'alt="A photo"' in sanitized


def test_https_img_with_all_allowed_attrs_survives():
    content = (
        "<p>Body</p>"
        '<img src="https://cdn.example.com/x.jpg" alt="alt"'
        ' width="800" height="600" loading="lazy">'
    )
    sanitized = sanitize_blog_content(content)

    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized
    assert 'alt="alt"' in sanitized
    assert 'width="800"' in sanitized
    assert 'height="600"' in sanitized
    assert 'loading="lazy"' in sanitized


# ─────────────────────────── Non-https src is dropped ─────────────────────────


def test_http_img_dropped():
    content = '<p>Body</p><img src="http://cdn.example.com/x.jpg">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized


def test_data_url_img_dropped():
    content = '<p>Body</p><img src="data:image/png;base64,iVBOR=">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized
    assert "data:" not in sanitized


def test_javascript_url_img_dropped():
    content = '<p>Body</p><img src="javascript:alert(1)">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized
    assert "javascript:" not in sanitized.lower()


def test_blob_url_img_dropped():
    content = '<p>Body</p><img src="blob:https://evil.example.com/abc">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized
    assert "blob:" not in sanitized


def test_file_url_img_dropped():
    content = '<p>Body</p><img src="file:///etc/passwd">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized


def test_relative_path_img_dropped():
    content = '<p>Body</p><img src="/relative/path.jpg">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized


def test_img_with_no_src_dropped():
    content = '<p>Body</p><img alt="orphan">'
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized


# ──────────────────────── Disallowed attributes are stripped ──────────────────


def test_onerror_attribute_is_stripped_but_https_img_survives():
    content = '<img src="https://cdn.example.com/x.jpg" onerror="alert(1)" alt="A">'
    sanitized = sanitize_blog_content(content)

    # The img itself survives because src is https://...
    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized
    # But onerror is stripped.
    assert "onerror" not in sanitized.lower()
    assert "alert(" not in sanitized


def test_srcset_attribute_is_stripped():
    content = (
        '<img src="https://cdn.example.com/x.jpg"'
        ' srcset="https://cdn.example.com/x@2x.jpg 2x" alt="A">'
    )
    sanitized = sanitize_blog_content(content)

    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized
    assert "srcset" not in sanitized.lower()


def test_style_attribute_is_stripped():
    content = '<img src="https://cdn.example.com/x.jpg" style="display:none" alt="A">'
    sanitized = sanitize_blog_content(content)

    assert "<img" in sanitized
    assert "style" not in sanitized.lower()


# ──────────────── Edge: img alone (no other editorial HTML) ───────────────────


def test_https_img_alone_triggers_html_path():
    """If content contains ONLY an <img> tag with no other editorial HTML,
    EDITORIAL_HTML_PATTERN must still detect it so sanitize_blog_content
    routes through bleach instead of returning the raw string.
    """
    content = '<img src="https://cdn.example.com/x.jpg" alt="A">'
    sanitized = sanitize_blog_content(content)

    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized


def test_javascript_img_alone_dropped_not_passed_through():
    """If only a malicious <img> is present and detection failed, the
    raw javascript: src would survive. This guards against EDITORIAL_HTML_PATTERN
    regression.
    """
    content = '<img src="javascript:alert(1)">'
    sanitized = sanitize_blog_content(content)

    assert "<img" not in sanitized
    assert "javascript:" not in sanitized.lower()


# ──────────────────────── Single-quoted src is handled ────────────────────────


def test_single_quoted_https_src_survives():
    content = "<p>Body</p><img src='https://cdn.example.com/x.jpg' alt='A'>"
    sanitized = sanitize_blog_content(content)

    # Bleach normalizes to double quotes — verify img+src made it through
    assert "<img" in sanitized
    assert "https://cdn.example.com/x.jpg" in sanitized


def test_single_quoted_http_src_dropped():
    content = "<p>Body</p><img src='http://insecure.example.com/x.jpg'>"
    sanitized = sanitize_blog_content(content)

    assert "<p>Body</p>" in sanitized
    assert "<img" not in sanitized


# ─────────────────── Regression: non-img sanitization unaffected ──────────────


def test_existing_unsafe_blocks_still_stripped():
    """Regression: pre-existing test from test_blog_content_utils.py.
    Adding img to allowlist must not affect script/style/javascript: handling."""
    content = (
        "<p>Safe intro</p>"
        '<script>alert("x")</script>'
        "<style>body{display:none;}</style>"
        "<h3>Section</h3>"
        '<a href="javascript:alert(1)">Bad link</a>'
    )
    sanitized = sanitize_blog_content(content)

    assert "<p>Safe intro</p>" in sanitized
    assert "<h3>Section</h3>" in sanitized
    assert "script" not in sanitized.lower()
    assert "style" not in sanitized.lower()
    assert "alert(" not in sanitized
    assert "javascript:" not in sanitized.lower()


def test_markdown_passthrough_still_works():
    """Regression: markdown content (no HTML) must still pass through
    untouched."""
    content = "# Title\n\n- one\n- two\n\nParagraph."
    assert sanitize_blog_content(content) == content


def test_mixed_content_with_img_and_other_tags():
    """End-to-end: a realistic synced article with paragraphs, headings,
    and an embedded image."""
    content = (
        "<h2>Section</h2>"
        "<p>Some text.</p>"
        '<img src="https://cdn.example.com/x.jpg" alt="Photo" width="800">'
        "<p>More text.</p>"
    )
    sanitized = sanitize_blog_content(content)

    assert "<h2>Section</h2>" in sanitized
    assert "<p>Some text.</p>" in sanitized
    assert "<img" in sanitized
    assert 'src="https://cdn.example.com/x.jpg"' in sanitized
    assert "<p>More text.</p>" in sanitized
