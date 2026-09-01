"""URL normalization and domain boundary utilities for crawling."""

from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


def normalize_crawl_url(url: str, base_url: str | None = None) -> str:
    """Normalize a crawl URL deterministically.

    Resolves relative URLs against base_url, lowercases scheme/host, removes default ports,
    strips fragments, collapses duplicate slashes in path, and sorts query parameters.
    """
    cleaned = url.strip()
    if base_url:
        cleaned = urljoin(base_url, cleaned)

    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return cleaned

    hostname = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port

    # Strip default ports
    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"

    # Path normalization
    path = parsed.path or "/"
    # Collapse double slashes while keeping leading slash
    parts: list[str] = []
    for segment in path.split("/"):
        if segment == "..":
            if parts:
                parts.pop()
        elif segment and segment != ".":
            parts.append(segment)

    normalized_path = "/" + "/".join(parts)
    if path.endswith("/") and normalized_path != "/":
        normalized_path += "/"

    # Sort query parameters for canonical URL representation
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    query_params.sort(key=lambda x: (x[0], x[1]))
    normalized_query = urlencode(query_params) if query_params else ""

    # Always strip fragments for crawl identity
    return urlunparse((scheme, netloc, normalized_path, "", normalized_query, ""))


def is_same_domain(target_url: str, allowed_host: str, include_subdomains: bool = False) -> bool:
    """Check whether target_url belongs to the verified website host boundary."""
    parsed = urlparse(target_url)
    target_host = parsed.hostname
    if not target_host:
        return False

    target_host = target_host.lower().strip()
    allowed_host = allowed_host.lower().strip()

    # Direct match or www prefix equivalence
    if target_host == allowed_host:
        return True

    # Strip www for comparison
    clean_target = target_host.removeprefix("www.")
    clean_allowed = allowed_host.removeprefix("www.")
    if clean_target == clean_allowed:
        return True

    return bool(include_subdomains and target_host.endswith(f".{clean_allowed}"))
