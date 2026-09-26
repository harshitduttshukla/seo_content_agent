"""Search Console property ↔ website coverage (Google's property semantics) and the
runtime database-role guard. Pure; no I/O."""

import pytest
from app.db.runtime_role import RuntimeRole
from app.domains.search_console.coverage import (
    domain_property,
    property_covers_website,
    url_prefix,
)

SHUKLA = "https://www.shuklascaffolding.com/"


@pytest.mark.parametrize(
    ("site_url", "website", "covered"),
    [
        # The required cases.
        ("sc-domain:shuklascaffolding.com", SHUKLA, True),
        ("https://www.shuklascaffolding.com/", SHUKLA, True),
        ("sc-domain:vrumo.in", SHUKLA, False),
        ("https://www.vrumo.in/", SHUKLA, False),
        ("sc-domain:vrumo.in", "https://www.vrumo.in/", True),
        ("https://www.vrumo.in/", "https://www.vrumo.in/", True),
        ("sc-domain:another-client.com", "https://www.vrumo.in/", False),
        # Domain properties cover the domain and every subdomain, on http and https.
        ("sc-domain:shuklascaffolding.com", "https://shuklascaffolding.com", True),
        ("sc-domain:shuklascaffolding.com", "http://blog.shuklascaffolding.com/news", True),
        ("sc-domain:www.shuklascaffolding.com", SHUKLA, True),
        ("sc-domain:www.shuklascaffolding.com", "https://shuklascaffolding.com/", False),
        # …but not a different domain that merely ends with the same letters.
        ("sc-domain:shuklascaffolding.com", "https://notshuklascaffolding.com/", False),
        ("sc-domain:scaffolding.com", SHUKLA, False),
        # URL-prefix properties: exact scheme and host; www and non-www differ.
        ("https://shuklascaffolding.com/", SHUKLA, False),
        ("http://www.shuklascaffolding.com/", SHUKLA, False),
        ("https://www.shuklascaffolding.com/", "https://shuklascaffolding.com/", False),
        # Normalization: case, trailing slash and dot, default port.
        ("https://WWW.ShuklaScaffolding.com/", "https://www.shuklascaffolding.com", True),
        ("https://www.shuklascaffolding.com:443/", "https://www.shuklascaffolding.com./", True),
        ("SC-DOMAIN:ShuklaScaffolding.COM", SHUKLA, True),
        ("https://www.shuklascaffolding.com:8443/", SHUKLA, False),
        # A prefix covers the website only when it is the website's path or a parent.
        ("https://www.shuklascaffolding.com/", "https://www.shuklascaffolding.com/in/", True),
        ("https://www.shuklascaffolding.com/in/", SHUKLA, False),
        (
            "https://www.shuklascaffolding.com/in/",
            "https://www.shuklascaffolding.com/india/",
            False,
        ),
        # Unusable values never match.
        ("sc-domain:com", "https://www.example.com/", False),
        ("sc-domain:", SHUKLA, False),
        ("sc-domain:shuklascaffolding.com/path", SHUKLA, False),
        ("ftp://www.shuklascaffolding.com/", SHUKLA, False),
        ("www.shuklascaffolding.com", SHUKLA, False),
        ("sc-domain:shuklascaffolding.com", "not a url", False),
    ],
)
def test_property_covers_website(site_url: str, website: str, covered: bool) -> None:
    assert property_covers_website(site_url, website) is covered


def test_internationalized_hosts_compare_in_idna_form() -> None:
    assert property_covers_website("sc-domain:xn--bcher-kva.example", "https://www.bücher.example/")
    assert property_covers_website("https://bücher.example/", "https://xn--bcher-kva.example")


def test_normalized_forms() -> None:
    prefix = url_prefix("HTTPS://Www.Example.com:443")
    assert prefix is not None
    assert (prefix.scheme, prefix.host, prefix.port, prefix.path) == (
        "https",
        "www.example.com",
        None,
        "/",
    )
    assert domain_property("sc-domain:Example.com.") == "example.com"
    assert domain_property("https://example.com/") is None


@pytest.mark.parametrize(
    ("role", "ok"),
    [
        (RuntimeRole("seo_content_app", False, False, ()), True),
        (RuntimeRole("postgres", True, True, ("websites",)), False),
        (RuntimeRole("bypass", False, True, ()), False),
        (RuntimeRole("owner", False, False, ("gsc_properties",)), False),
    ],
)
def test_runtime_role_problems(role: RuntimeRole, ok: bool) -> None:
    assert (role.problems() == []) is ok
