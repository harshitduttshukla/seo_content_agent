"""Unit tests for crawler security, parsers, and extractors."""

import pytest
from app.domains.content.extractors.html import HtmlContentExtractor
from app.domains.crawling.parsers.robots import RobotsParser
from app.domains.crawling.parsers.sitemap import SitemapParser
from app.domains.crawling.security.ssrf import SSRFSecurityError, validate_safe_url
from app.domains.crawling.security.url import is_same_domain, normalize_crawl_url


def test_url_normalization() -> None:
    # Scheme and host lowercasing, fragment stripping
    assert (
        normalize_crawl_url("HTTPS://Example.COM:443/Path/To/Page#section")
        == "https://example.com/Path/To/Page"
    )
    # Default port stripping for HTTP (80)
    assert normalize_crawl_url("http://example.com:80/docs/") == "http://example.com/docs/"
    # Relative path resolution
    assert (
        normalize_crawl_url("../about", base_url="https://example.com/products/software")
        == "https://example.com/about"
    )
    # Query parameter sorting
    assert (
        normalize_crawl_url("https://example.com/shop?b=2&a=1&c=3")
        == "https://example.com/shop?a=1&b=2&c=3"
    )


def test_domain_boundary_checks() -> None:
    assert is_same_domain("https://example.com/blog", "example.com") is True
    assert is_same_domain("https://www.example.com/blog", "example.com") is True
    assert is_same_domain("https://example.com/blog", "www.example.com") is True
    assert (
        is_same_domain("https://sub.example.com/blog", "example.com", include_subdomains=False)
        is False
    )
    assert (
        is_same_domain("https://sub.example.com/blog", "example.com", include_subdomains=True)
        is True
    )
    assert (
        is_same_domain("https://otherdomain.com", "example.com", include_subdomains=True) is False
    )


def test_ssrf_validator_blocks_private_and_metadata_ips() -> None:
    # Direct private IPv4
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://127.0.0.1/admin", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://10.0.0.5/api", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://192.168.1.1/", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://172.16.0.1/", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://169.254.169.254/latest/meta-data/", resolve_dns=False)

    # Localhost hostnames
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://localhost:8080/metrics", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://test.localhost/", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("http://metadata.google.internal/computeMetadata/v1/", resolve_dns=False)

    # Disallowed protocols
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("file:///etc/passwd", resolve_dns=False)
    with pytest.raises(SSRFSecurityError):
        validate_safe_url("ftp://example.com/dump.tar.gz", resolve_dns=False)


def test_robots_txt_parser() -> None:
    robots_content = """
    User-agent: *
    Disallow: /admin/
    Disallow: /private/
    Allow: /admin/public/
    Allow: /articles/*.html$
    Crawl-delay: 1.5
    Sitemap: https://example.com/sitemap.xml
    Sitemap: https://example.com/sitemap-news.xml
    """

    parser = RobotsParser(robots_content)
    assert parser.crawl_delay == 1.5
    assert len(parser.sitemaps) == 2
    assert "https://example.com/sitemap.xml" in parser.sitemaps

    # Allowed by default
    assert parser.can_fetch("https://example.com/about") is True
    # Disallowed path
    assert parser.can_fetch("https://example.com/admin/settings") is False
    # Allowed subpath overrides disallow
    assert parser.can_fetch("https://example.com/admin/public/help") is True
    # Wildcard matching
    assert parser.can_fetch("https://example.com/articles/seo-guide.html") is True


def test_sitemap_parser_standard() -> None:
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <url>
          <loc>https://example.com/</loc>
          <lastmod>2026-09-01</lastmod>
          <changefreq>daily</changefreq>
          <priority>1.0</priority>
       </url>
       <url>
          <loc>https://example.com/pricing</loc>
          <lastmod>2026-08-15</lastmod>
          <priority>0.8</priority>
       </url>
    </urlset>
    """
    result = SitemapParser.parse(xml_content)
    assert result.is_index is False
    assert len(result.urls) == 2
    assert result.urls[0].loc == "https://example.com/"
    assert result.urls[0].priority == 1.0
    assert result.urls[1].loc == "https://example.com/pricing"
    assert result.urls[1].priority == 0.8


def test_sitemap_parser_index() -> None:
    xml_index = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <sitemap>
          <loc>https://example.com/sitemap-posts.xml</loc>
       </sitemap>
       <sitemap>
          <loc>https://example.com/sitemap-categories.xml</loc>
       </sitemap>
    </sitemapindex>
    """
    result = SitemapParser.parse(xml_index)
    assert result.is_index is True
    assert len(result.child_sitemaps) == 2
    assert "https://example.com/sitemap-posts.xml" in result.child_sitemaps


def test_html_content_extractor() -> None:
    html = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Ultimate Guide to Technical SEO</title>
        <meta name="description"
              content="A comprehensive deep dive into technical SEO and structured data." />
        <link rel="canonical" href="https://example.com/seo-guide" />
        <meta property="og:title" content="Technical SEO Guide" />
        <meta name="robots" content="index, follow" />
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Article", "headline": "SEO"}
        </script>
    </head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <main>
            <h1>Ultimate Guide to Technical SEO</h1>
            <p>Welcome to our comprehensive guide on crawling and indexing.</p>
            <h2>Crawling Mechanics</h2>
            <p>Search engines discover pages via links and sitemaps.</p>
            <ul>
                <li>Robots.txt parsing</li>
                <li>Canonical resolution</li>
            </ul>
            <img src="/assets/seo-diagram.png"
                 alt="Architecture diagram"
                 width="800"
                 height="600" />
            <a href="/pricing" rel="nofollow">Check Pricing</a>
            <a href="https://google.com" rel="noopener sponsored">External Resource</a>
        </main>
        <footer><p>&copy; 2026 Example Corp</p></footer>
    </body>
    </html>
    """

    extractor = HtmlContentExtractor(base_host="example.com")
    extracted = extractor.extract(html, "https://example.com/seo-guide")

    assert extracted.title == "Ultimate Guide to Technical SEO"
    assert (
        extracted.meta_description
        == "A comprehensive deep dive into technical SEO and structured data."
    )
    assert extracted.canonical_url == "https://example.com/seo-guide"
    assert extracted.language == "en"

    # Headings
    assert len(extracted.headings) == 2
    assert extracted.headings[0]["level"] == 1
    assert extracted.headings[0]["text"] == "Ultimate Guide to Technical SEO"
    assert extracted.headings[1]["level"] == 2
    assert extracted.headings[1]["text"] == "Crawling Mechanics"

    # Structured document blocks
    blocks = extracted.structured_content["blocks"]
    assert isinstance(blocks, list)
    assert any(isinstance(b, dict) and b.get("type") == "heading" for b in blocks)
    assert any(isinstance(b, dict) and b.get("type") == "paragraph" for b in blocks)
    assert any(isinstance(b, dict) and b.get("type") == "list_item" for b in blocks)

    # Links
    assert len(extracted.links) >= 2
    internal_links = [link for link in extracted.links if link.is_internal]
    external_links = [link for link in extracted.links if not link.is_internal]

    assert len(internal_links) >= 1
    assert internal_links[0].normalized_target_url in (
        "https://example.com/pricing",
        "https://example.com/home",
    )
    assert any(link.nofollow for link in extracted.links)
    assert any(link.sponsored for link in external_links)

    # Images
    assert len(extracted.images) == 1
    assert extracted.images[0]["alt"] == "Architecture diagram"
    assert extracted.images[0]["width"] == 800

    # Content hash
    assert len(extracted.content_hash) == 64
    assert extracted.word_count > 10


def test_html_extractor_resilience_to_oversized_fields_and_null_bytes() -> None:
    """Verify that oversized titles, rels, and null bytes are sanitized and bounded."""
    oversized_title = "T" * 800 + "\x00weird"
    oversized_rel = "nofollow " * 30 + "\x00"
    oversized_anchor = "A" * 700 + "\x00text"
    oversized_meta = "M" * 1500 + "\x00desc"
    body_with_null = "Hello\x00 world! This is a test paragraph with null bytes."

    html = f"""
    <!DOCTYPE html>
    <html lang="en-US-very-long-locale-string-here">
    <head>
        <title>{oversized_title}</title>
        <meta name="description" content="{oversized_meta}">
    </head>
    <body>
        <h1>Heading\x00 with null</h1>
        <p>{body_with_null}</p>
        <a href="/test" rel="{oversized_rel}">{oversized_anchor}</a>
        <img src="/img.png" alt="{"Alt" * 500}" title="{"Title" * 300}">
    </body>
    </html>
    """

    extractor = HtmlContentExtractor(base_host="example.com")
    extracted = extractor.extract(html, "https://example.com")

    # Title capped at 500, no null byte
    assert len(extracted.title) <= 500
    assert "\x00" not in extracted.title

    # Language capped at 20, no null byte
    assert len(extracted.language) <= 20
    assert "\x00" not in extracted.language

    # Meta description capped at 1000, no null byte
    assert len(extracted.meta_description) <= 1000
    assert "\x00" not in extracted.meta_description

    # Headings and clean content free of null bytes
    assert all("\x00" not in str(h.get("text", "")) for h in extracted.headings)
    assert "\x00" not in extracted.cleaned_content

    # Links capped
    assert len(extracted.links) == 1
    assert len(extracted.links[0].anchor_text) <= 500
    assert "\x00" not in extracted.links[0].anchor_text
    assert extracted.links[0].rel is not None
    assert len(extracted.links[0].rel) <= 120
    assert "\x00" not in extracted.links[0].rel

    # Images capped
    assert len(extracted.images) == 1
    assert len(str(extracted.images[0].get("alt", ""))) <= 1000
    assert len(str(extracted.images[0].get("title", ""))) <= 500
