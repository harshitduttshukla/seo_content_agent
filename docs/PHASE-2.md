# Phase 2 — Website & Content Intelligence Foundation

## 1. Overview & Objective

Phase 2 transitions connected project websites from static database entities into active, structured, crawlable, and searchable content intelligence sources. It establishes the deterministic baseline of data required before any AI reasoning or recommendations can occur.

```text
Website
    ↓
Domain Verification (HTML meta / HTTP header / well-known file)
    ↓
robots.txt Parser & Sitemap Discovery
    ↓
SSRF-Safe Async Crawler (Bounded concurrency, rate limiting, redirects)
    ↓
Deterministic HTML & Content Extractor (Headings H1–H6, structured blocks, links, images, canonicals)
    ↓
Content Normalizer & Deduplication (SHA-256 content_hash)
    ↓
Structured Page & Version Storage (content_pages, content_page_versions, page_links)
    ↓
Content Inventory & Search APIs
```

---

## 2. Core Components Built in Phase 2

### 1. Website Verification Service
- Proves domain ownership before crawling is permitted.
- Generates deterministic verification tokens: `ag-verify-<hash>`.
- Verification methods supported:
  - `http_meta`: Checks homepage HTML for `<meta name="antigravity-verification" content="...">`.
  - `verification_file`: Checks `/.well-known/antigravity-verification.txt`.
  - `http_header`: Checks custom response header `X-Antigravity-Verification`.
- State transitions: `unverified` -> `verified` or `failed`.
- Audit logged (`website.verified`) and published to outbox.

### 2. SSRF Security & URL Safety Layer
- Validates every URL before fetching and on every redirect hop.
- Disallows non-HTTP/HTTPS schemes (e.g. `file://`, `ftp://`).
- Resolves DNS and blocks IPv4 & IPv6 loopbacks (`127.0.0.0/8`, `::1`), RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), Link-Local addresses (`169.254.0.0/16`, AWS metadata `169.254.169.254`), and cloud internal hostnames (`metadata.google.internal`).
- Enforces response size limits (5 MB max) and max redirect hops (5 max).

### 3. Robots.txt & Sitemap Discovery
- `RobotsParser`: Parses User-agent directives, wildcard matching (`*`, `$`), `Allow`/`Disallow` specificity, `Crawl-delay`, and `Sitemap:` directives.
- `SitemapParser`: Extracts URLs, `lastmod`, `changefreq`, `priority`, and recursively navigates sitemap indexes.

### 4. Crawl Frontier & Async Job Engine
- Queue prioritization (sitemaps > seeds > discovered internal links).
- Depth tracking (`max_depth`), domain boundary filter (`same_host`/`include_subdomains`), deduplication on `normalized_url`.
- Asynchronous execution with cancellation checkpoints.

### 5. Content Extractor & Normalizer
- Deterministic extraction using BeautifulSoup / lxml without headless browsers.
- Extracted elements:
  - Title, meta description, language, canonical URL.
  - Headings hierarchy (H1–H6) in document order.
  - Structured document blocks (headings, paragraphs, lists) in JSONB.
  - Image metadata (`src`, `alt`, `title`, dimensions).
  - Internal and external links with attributes (`rel`, `nofollow`, `ugc`, `sponsored`).
- SHA-256 `content_hash` computation on normalized text.

### 6. Storage & Versioning
- `content_pages`: Central inventory of crawlable pages.
- `content_page_versions`: Created whenever `content_hash` changes on subsequent crawls.
- `page_links`: Discovered link edges forming the raw foundation for future internal linking graphs.

---

## 3. Database Schema

- `crawl_jobs`: Tracks asynchronous crawl jobs, configuration, progress counts, and status (`queued`, `running`, `completed`, `failed`, `cancelled`).
- `crawl_urls`: URL inventory with status (`discovered`, `crawled`, `failed`, `blocked`), response times, and HTTP statuses.
- `crawl_events`: Structured event log per crawl job.
- `content_pages`: Structured indexed pages with JSONB headings, images, metadata, and structured blocks.
- `content_page_versions`: Version history tracking text diffs across crawls.
- `page_links`: Edge table of internal and external hyperlinks.

Migration: `apps/api/alembic/versions/20260901_0002_phase2_crawling_content.py`.

---

## 4. API Endpoints

- `GET /api/v1/websites/{id}/verification`: Retrieve verification token and snippets.
- `POST /api/v1/websites/{id}/verify`: Trigger active ownership verification check.
- `GET /api/v1/websites/{id}/crawl-status`: Get active crawl progress and stats.
- `POST /api/v1/websites/{id}/crawl`: Initiate crawl job.
- `GET /api/v1/websites/{id}/crawl-jobs`: List historical crawl jobs.
- `GET /api/v1/crawl-jobs/{id}`: Inspect specific crawl job details.
- `POST /api/v1/crawl-jobs/{id}/cancel`: Cancel a running crawl.
- `GET /api/v1/websites/{id}/pages`: Search and filter indexed page inventory.
- `GET /api/v1/websites/{id}/pages/{page_id}`: Inspect structured page metadata, headings, and images.
- `GET /api/v1/websites/{id}/links`: List discovered links for link graph analysis.

---

## 5. Verification & Testing

- Unit tests: `tests/unit/test_crawling_parsers.py` (SSRF, URL normalizer, RobotsParser, SitemapParser, HtmlExtractor).
- API integration tests: `tests/api/test_crawling_api.py` (verification, crawl jobs, cancellation, page inventory).
- Frontend tests: `apps/web/src/__tests__/crawling-components.test.tsx` (CrawlPanel, PageInventory, WebsiteWorkspace tabs).
- Static analysis: `ruff check` (clean), `mypy` (clean), `openapi-typescript` (clean).
