# AI SEO Content Harness Guide

The **Content Harness** is a dedicated, controlled testing and evaluation environment for our AI SEO content generation pipeline.

---

## 1. What is the Content Harness?

The Content Harness is a "test bench" for AI-generated content. Just like an electrical engineer tests an electronic component on a test harness before soldering it into a finished device, our Content Harness allows us to test, evaluate, compare, and refine prompt strategies and AI content generation without touching or mutating live production documents.

---

## 2. Why Are We Building It?

Before connecting complex multi-step agents or automated workflows in the AI Orchestrator, we need to answer a fundamental question:

> *"Is our AI generating high-quality, brand-compliant, search-optimized content?"*

If our content generation pipeline is flawed, automating it with an orchestrator will only produce bad content faster. The harness gives us:
- **Reproducibility**: Run the exact same content scenario repeatedly.
- **Measurability**: Score output with clear mathematical rules (0–100) instead of vague human impressions.
- **Safety**: Test prompt changes (e.g. Prompt V1 vs. Prompt V2) without modifying production databases or user documents.
- **Transparency**: Easily inspect what goes into the AI, what comes out, and exactly why it passed or failed.

---

## 3. Input Structure

Every harness run starts with a typed input (`ContentHarnessInput`):

| Field | Type | Description |
| :--- | :--- | :--- |
| `project_id` | `UUID` | Scope identifier ensuring tenant isolation. |
| `primary_keyword` | `string` | The target search term (e.g., `"fleet vehicle tracking"`). |
| `secondary_keywords` | `list[string]` | Supporting semantic keywords to cover. |
| `search_intent` | `string` | User intent (e.g., `INFORMATIONAL`, `COMMERCIAL`). |
| `target_audience` | `string` | Who the article is written for (e.g., `"Fleet managers"`). |
| `target_word_count` | `int` | Goal length (e.g., `1200` words). |
| `required_topics` | `list[string]` | Core topics that must be addressed. |
| `required_questions` | `list[string]` | Questions to answer (e.g. FAQ or section headers). |
| `brand_rules` | `BrandRequirements` | Tone, voice, style, and strictly forbidden words. |
| `internal_link_targets`| `list[InternalLinkTarget]`| Approved URLs and anchor texts to integrate. |
| `website_context` | `string` | Verified business context to ground facts and prevent hallucinations. |
| `prompt_version` | `string` | Which prompt template to use (e.g., `"v1"` or `"v2"`). |

---

## 4. Context Assembly

Before sending instructions to the AI, the harness builds a **Context Snapshot**:
1. **Direct Inputs**: Uses the inputs passed into the run.
2. **Optional Brief Integration**: If `content_brief_id` is supplied, loads approved brief parameters from the database.
3. **Anti-Injection Fencing**: Wraps external context in `<WEBSITE_CONTEXT>` and `<CONTENT_HARNESS_REQUEST>` fences so retrieved context is treated as reference data, never as system instructions.

---

## 5. Prompt Construction & Versioning

The harness decouples the **System Prompt** (instructions and output schema) from the **User Prompt** (data and specifications).

- **Prompt V1 (`v1`)**: Baseline structured article generator specifying H1, meta description, H2 sections, keyword placement, and JSON output format.
- **Prompt V2 (`v2`)**: Enhanced prompt with stricter negative constraints (zero forbidden words, exact anchor text matching, calibrated keyword density, and strict factual boundaries).
- **Custom Prompts**: Allows prompt engineers to supply experimental system prompts to test novel prompting techniques.

Every run records the exact system prompt, user prompt, and generation parameters so past runs can always be reproduced.

---

## 6. AI Provider Interaction

The harness calls the application's unified `AIProvider` abstraction (`apps/api/app/ai/provider.py`):
- In production / live test: Calls `GeminiAIProvider` using Google Gemini models.
- In automated tests / offline dev: Calls `MockAIProvider` for deterministic, zero-cost execution.
- No direct SDK dependencies (no LangChain, LangGraph, or CrewAI).

---

## 7. Structured Output Format

The AI responds with structured JSON validating against `HarnessGeneratedContent`:

```json
{
  "title": "Complete Guide to Fleet Vehicle Tracking",
  "meta_description": "Discover how fleet vehicle tracking optimizes vehicle operations and reduces overhead costs.",
  "content": "Full markdown content...",
  "sections": [
    {
      "heading": "Core Benefits of Fleet Vehicle Tracking",
      "level": 2,
      "content": "A primary advantage is substantial operational efficiency..."
    }
  ],
  "used_keywords": ["fleet vehicle tracking", "gps tracking"],
  "internal_links": [
    {
      "url": "/telematics-platform",
      "anchor_text": "telematics platform"
    }
  ],
  "word_count": 1240
}
```

---

## 8. Deterministic Evaluation Rules

Content quality is evaluated using clear, explainable deterministic algorithms:

### SEO Score (0–100)
1. **Primary Keyword in Title (+25 pts)**: Primary keyword must appear in the H1 title.
2. **Primary Keyword in Introduction (+20 pts)**: Must appear in the first 150 words.
3. **Primary Keyword in Headings (+15 pts)**: Must appear in at least one H2 heading.
4. **Secondary Keyword Coverage (+25 pts)**: Points awarded proportionally to the fraction of secondary keywords found.
5. **Keyword Density (+15 pts)**: Evaluates primary keyword density. Healthy range: 0.4%–2.8%. If density > 3.0%, flags keyword stuffing risk.

### Content Coverage Score (0–100)
1. **Word Count Tolerance (+30 pts)**: Awarded if total word count is within ±20% of target word count.
2. **Required Topics Covered (+35 pts)**: Verified against section headings and body content.
3. **Questions Addressed (+25 pts)**: Checks if required questions are answered in text.
4. **Heading Structure (+10 pts)**: Checks for multiple distinct H2 sections without duplicate headings.

### Brand Compliance Score (0–100)
1. **Forbidden Words**: Starts at 100 base. **-25 points for every forbidden word detected**, and registers a `HIGH` impact failure.
2. **Tone & Style**: Checks presence of tone specifications and formatting compliance.

### Internal Linking Score (0–100)
1. **Approved Link Targets (+80 pts)**: Verified against required URLs and anchor texts.
2. **Link Integrity (+20 pts)**: Checks for duplicate link targets or broken formatting.

### Technical Validity (PASS / FAIL)
- Valid JSON schema compliance.
- Non-empty title and content.
- At least one structured section.

---

## 9. Scorecard & Status

The overall score is a weighted composite:

$$\text{Overall Score} = (0.30 \times \text{SEO}) + (0.30 \times \text{Content}) + (0.20 \times \text{Brand}) + (0.20 \times \text{Linking})$$

- **Status = PASS**: Technical validity is `PASS`, Brand score $\ge 70$, no high-impact failures, and Overall Score $\ge 75$.
- **Status = NEEDS IMPROVEMENT**: Any critical failure, forbidden word, or overall score $< 75$.

---

## 10. Run History & Database Storage

All test runs are persisted in PostgreSQL in the `content_harness_runs` table:
- Scoped to `(organization_id, project_id)`.
- Records inputs, context snapshot, prompt data, output data, scorecard findings, and timestamps.
- Indexed for fast retrieval by project and creation date.

---

## 11. How to Create a New Test Case

1. Navigate to **Content Harness** in the project sidebar (`/projects/[projectId]/content-harness`).
2. Select a benchmark from **Standard Golden Test Cases** (e.g., *Case 1: Normal SEO Article*, *Case 3: Brand Compliance*), or enter custom parameters.
3. Choose the prompt version (`v1` or `v2`).
4. Click **Run Content Harness**.
5. View the real-time scorecard, findings breakdown, and generated article.

---

## 12. How to Compare Two Runs

1. Go to the **Compare Runs** tab in the harness UI.
2. Select **Run A (Baseline)** and **Run B (Comparison)**.
3. Click **Compare Runs**.
4. The system calculates:
   - Metric score deltas (e.g. $\Delta \text{SEO}: +20.0$, $\Delta \text{Overall}: +15.0$).
   - Specific rule improvements (rules that failed in Run A but pass in Run B).
   - Regressions (rules that passed in Run A but degraded in Run B).

---

## 13. What the Harness Does NOT Do

To maintain safety and architectural integrity:
- ❌ **Does NOT mutate live documents**: Does not edit `content_documents` or `content_pages`.
- ❌ **Does NOT publish content**: Does not push to CMS or publish endpoints.
- ❌ **Does NOT modify SEO strategies**: Strategy and keyword mappings remain unchanged.
- ❌ **Does NOT run multi-agent loops**: Single deterministic turn (Input → AI → Output → Score).
- ❌ **Does NOT bypass tenant security**: Requires valid authenticated user credentials and project access.
