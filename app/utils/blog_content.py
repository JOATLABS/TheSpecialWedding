"""
Utilities for normalizing and sanitizing public blog article content.
"""
from __future__ import annotations

import re

import bleach

BLOG_ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "input",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
]

BLOG_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "input": ["checked", "disabled", "type"],
    "td": ["align"],
    "th": ["align"],
}

BLOG_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]

EDITORIAL_HTML_PATTERN = re.compile(
    r"</?(?:a|blockquote|br|code|del|em|h[1-6]|hr|input|li|ol|p|pre|strong|table|tbody|td|tfoot|th|thead|tr|ul)\b[^>]*>",
    re.IGNORECASE,
)
UNSAFE_BLOCK_PATTERN = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
    re.IGNORECASE | re.DOTALL,
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
WORD_PATTERN = re.compile(r"\b[\w'-]+\b")


def strip_unsafe_blog_blocks(content: str) -> str:
    """Remove whole unsafe blocks before sanitization so their inner text is not preserved."""
    if not content:
        return ""

    without_comments = HTML_COMMENT_PATTERN.sub("", content)
    return UNSAFE_BLOCK_PATTERN.sub("", without_comments)


def blog_content_contains_html(content: str) -> bool:
    """Detect supported editorial HTML without misclassifying plain markdown."""
    if not content:
        return False

    return bool(EDITORIAL_HTML_PATTERN.search(content))


def sanitize_blog_content(content: str) -> str:
    """Keep markdown untouched, but sanitize supported editorial HTML."""
    if not isinstance(content, str):
        return ""

    normalized = strip_unsafe_blog_blocks(content).strip()
    if not normalized:
        return ""

    if not blog_content_contains_html(normalized):
        return normalized

    return bleach.clean(
        normalized,
        tags=BLOG_ALLOWED_TAGS,
        attributes=BLOG_ALLOWED_ATTRIBUTES,
        protocols=BLOG_ALLOWED_PROTOCOLS,
        strip=True,
    ).strip()


def blog_content_word_count(content: str) -> int:
    """Estimate reading time from visible content rather than raw HTML markup."""
    sanitized = sanitize_blog_content(content)
    if not sanitized:
        return 0

    text_only = (
        bleach.clean(sanitized, tags=[], strip=True)
        if blog_content_contains_html(sanitized)
        else sanitized
    )
    return len(WORD_PATTERN.findall(text_only))
