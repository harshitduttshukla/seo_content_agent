# Content Indexing & Versioning Architecture

## 1. Structured Representation

Rather than storing only raw or unparsed HTML, Phase 2 normalizes and structures page data into several representations:

1. **Structured Headings (H1–H6)**: Preserves the semantic heading hierarchy in document order.
2. **Structured Document Blocks**: JSON representation with typed block nodes (`heading`, `paragraph`, `list_item`). This format is directly compatible with future TipTap editor models and AI retrieval chunkers.
3. **Clean Prose Content**: Noise-stripped plain text for word counts and hashing.
4. **Metadata & Signals**: Title, meta description, canonical URL, language, OpenGraph, Twitter cards, schema JSON-LD, robots directives.
5. **Link Graph Foundations**: Discovered hyperlinks recorded in `page_links` with `is_internal`, `rel`, `nofollow`, `ugc`, and `sponsored` flags.
6. **Images Metadata**: Image `src`, `alt`, and `title` for future image SEO guidance.

---

## 2. Content Hashing & Versioning

- Each page computes a deterministic SHA-256 `content_hash` from the normalized title and body text.
- If a subsequent crawl detects a changed `content_hash`, a new immutable record is appended to `content_page_versions`.
- If the content hash is unchanged, the version history is preserved without duplicate rows.
- Duplicate content across different URLs within the website is flagged (`content_status = "duplicate"`).

---

## 3. Preparation for Future Phases

| Future Feature | Prepared By Phase 2 |
|---|---|
| **Content Map & Architecture** | `content_pages` inventory with URL hierarchy and headings |
| **Internal Linking Recommendations** | `page_links` table with source/target relationships and anchor text |
| **SEO Rule Evaluation** | Extracted canonicals, titles, meta descriptions, H1 presence, image alt tags |
| **Semantic Embeddings & pgvector** | Clean structured blocks (`structured_content`) ready for chunking without HTML noise |
