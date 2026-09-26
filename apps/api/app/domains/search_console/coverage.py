"""Does a Search Console property cover a website? Pure; no I/O.

Google's property types:

- Domain property ``sc-domain:example.com`` covers every URL on example.com and on
  any subdomain of it (www., m., …), over http and https.
- URL-prefix property ``https://www.example.com/`` covers only URLs that start with
  exactly that scheme, host, port and path; http/https and www/non-www are separate
  properties.

A website is covered when every URL under its base URL is covered, so a URL-prefix
property must be the website's base URL or a parent path of it. Hosts are compared
after lower-casing, removing a trailing dot and IDNA encoding; default ports are
ignored. Raw strings are never compared.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

DOMAIN_PREFIX = "sc-domain:"
DEFAULT_PORTS = {"http": 80, "https": 443}
_HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*$")


@dataclass(frozen=True, slots=True)
class UrlPrefix:
    scheme: str
    host: str
    port: int | None  # None: the scheme's default port
    path: str  # always ends with "/"


def normalize_host(value: str) -> str | None:
    host = value.strip().rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if not _HOST.match(host) or any(len(label) > 63 for label in host.split(".")):
        return None
    return host


def url_prefix(url: str) -> UrlPrefix | None:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS or not parts.hostname:
        return None
    host = normalize_host(parts.hostname)
    if host is None:
        return None
    path = parts.path or "/"
    return UrlPrefix(
        scheme,
        host,
        None if port in (None, DEFAULT_PORTS[scheme]) else port,
        path if path.endswith("/") else f"{path}/",
    )


def domain_property(site_url: str) -> str | None:
    """The domain of an ``sc-domain:`` property, or None for any other value."""
    if not site_url.lower().startswith(DOMAIN_PREFIX):
        return None
    domain = normalize_host(site_url[len(DOMAIN_PREFIX) :])
    # A verifiable domain has at least two labels; a bare suffix would cover everything.
    return domain if domain and "." in domain else None


def property_covers_website(site_url: str, website_url: str) -> bool:
    website = url_prefix(website_url)
    if website is None:
        return False
    if site_url.lower().startswith(DOMAIN_PREFIX):
        domain = domain_property(site_url)
        return domain is not None and (
            website.host == domain or website.host.endswith(f".{domain}")
        )
    prefix = url_prefix(site_url)
    return (
        prefix is not None
        and (prefix.scheme, prefix.host, prefix.port)
        == (website.scheme, website.host, website.port)
        and website.path.startswith(prefix.path)
    )
