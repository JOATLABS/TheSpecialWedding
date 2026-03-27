from app.utils.blog_content import (
    blog_content_word_count,
    sanitize_blog_content,
)


def test_sanitize_blog_content_preserves_markdown():
    content = "# Pricing guide\n\n- One\n- Two"

    assert sanitize_blog_content(content) == content


def test_sanitize_blog_content_strips_unsafe_blocks_but_keeps_editorial_html():
    content = (
        '<p>Safe intro</p>'
        '<script>alert("x")</script>'
        '<style>body{display:none;}</style>'
        '<h3>Section</h3>'
        '<a href="javascript:alert(1)">Bad link</a>'
    )

    sanitized = sanitize_blog_content(content)

    assert '<p>Safe intro</p>' in sanitized
    assert '<h3>Section</h3>' in sanitized
    assert 'Bad link' in sanitized
    assert 'script' not in sanitized.lower()
    assert 'style' not in sanitized.lower()
    assert 'alert(' not in sanitized
    assert 'javascript:' not in sanitized.lower()


def test_blog_content_word_count_uses_visible_text_for_html():
    content = '<p>One two three</p><p><strong>Four</strong> five</p>'

    assert blog_content_word_count(content) == 5
