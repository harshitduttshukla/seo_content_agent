# Content Architecture, Mappings & Opportunities

## Content Hierarchy

```
Strategic Pillar
      ↓
    Topic
      ↓
Keyword Cluster
      ↓
Target Page (Existing or New Page Opportunity)
```

1. **Content Pillars (`content_pillars`)**: Top-level strategic themes aligned with core business goals (e.g. *Technical SEO*, *B2B Marketing*).
2. **Topics (`topics`)**: Sub-themes nested under pillars.
3. **Keyword Clusters (`keyword_clusters`)**: Groups of search queries targeting a specific topic.
4. **Target Pages (`content_pages`)**: Crawled live site URLs mapped to clusters.

---

## Keyword-to-Page Semantic Mapping

The mapping engine analyzes project keywords against all crawled pages on the site using deterministic multi-tier matching:
1. **URL Slug Match**: +0.50 score if keyword appears in URL path.
2. **Title Tag Match**: +0.40 score if keyword or tokens appear in HTML `<title>`.
3. **Heading Match**: +0.30 score if keyword is found in `<h1>` or `<h2>` headings.
4. **Body Content Match**: +0.20 score if exact keyword phrase appears in cleaned body text.

### Mapping Classification
- **`PRIMARY_TARGET`** ($\ge 0.70$ match): Strong alignment between page and keyword search intent.
- **`SECONDARY_TARGET`** ($0.45 \le \text{match} < 0.70$): Partial coverage. Page should be updated or expanded.
- **`NEW_PAGE_REQUIRED`** ($< 0.45$ match): No existing page covers this intent; generates a **New Page Opportunity**.

---

## Keyword Cannibalization Detection

Identifies SEO risks where multiple live pages compete for the same query by evaluating:
- Competing pages with exact keyword phrase in `<title>` or `<h1>`.
- Emits a `HIGH` severity warning when $> 2$ pages collide.
- Surfaced directly in the UI without automatic merges, allowing human SEOs to decide whether to 301 redirect, canonicalize, or differentiate the content.

---

## Content Opportunities & Gaps

- Automatically synthesizes gaps from unmapped clusters and secondary mappings into actionable opportunities:
  - `NEW_PAGE`
  - `UPDATE_EXISTING_PAGE`
- Follows the governed lifecycle (`proposed` -> `approved` / `rejected`).
- Ready for Phase 4 Content Planning and Brief Generation.
