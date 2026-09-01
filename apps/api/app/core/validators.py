"""Pure normalization helpers used at domain boundaries."""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from pydantic import HttpUrl

_SLUG_SEPARATOR = re.compile(r"[^a-z0-9]+")


def normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    slug = _SLUG_SEPARATOR.sub("-", normalized).strip("-")
    if not slug:
        raise ValueError("A slug must contain at least one letter or number.")
    return slug[:80].rstrip("-")


def normalize_website_url(value: HttpUrl | str) -> tuple[str, str]:
    parsed = urlsplit(str(value))
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise ValueError("Website URL must include a valid host.")
    port = parsed.port
    default_port = (parsed.scheme == "https" and port == 443) or (
        parsed.scheme == "http" and port == 80
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path.rstrip("/")
    normalized = urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))
    return normalized, host
