from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import InvalidCursor
from app.core.validators import normalize_slug, normalize_website_url
from pydantic import HttpUrl


def test_cursor_round_trip() -> None:
    timestamp = datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
    resource_id = uuid4()

    result = decode_cursor(encode_cursor(timestamp, resource_id))

    assert result is not None
    assert result.created_at == timestamp
    assert result.resource_id == resource_id


def test_invalid_cursor_is_a_safe_application_error() -> None:
    with pytest.raises(InvalidCursor):
        decode_cursor("not-a-cursor")


def test_slug_and_url_normalization() -> None:
    assert normalize_slug("  Growth & SEO  ") == "growth-seo"
    assert normalize_website_url(HttpUrl("HTTPS://Example.COM:443/blog/")) == (
        "https://example.com/blog",
        "example.com",
    )
