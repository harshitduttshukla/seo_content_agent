# SEO Rules and Validation Architecture

## 1. Objective

The SEO guide is an executable, versioned policy, not a prose checklist. A human-readable guide is rendered from active structured rules. Each analysis binds an exact content/page snapshot to an exact rule-set manifest so results can be reproduced and compared.

## 2. Rule contract

Conceptual Pydantic shape:

```python
class SeoRuleDefinition(BaseModel):
    schema_version: int
    key: str
    category: RuleCategory
    evaluation_type: Literal["deterministic", "ai"]
    severity: Literal["info", "warning", "error", "blocking"]
    applicability: Applicability
    parameters: dict[str, JSONValue]
    message_template: str
    remediation_template: str
```

The stored row also has rule ID/version, project/tenant, status, approval/provenance, and supersession. `parameters` is discriminated and validated by category-specific Pydantic models; a generic dictionary is only the conceptual union. Rules can inherit from a read-only system template by copying/versioning into the project—runtime results never change because a global template was edited.

Applicability filters website, locale, content type, page status, intent, and optional path pattern. Conflicting applicable rules fail rule-set activation unless an explicit precedence model resolves them. Evaluation output includes rule ID/version, evaluator/version, pass/fail/not-applicable/error, observed value, expected value, evidence location, severity, remediation, and duration.

## 3. Rule categories

| Category | Deterministic checks | AI-assisted checks (separately labeled) |
|---|---|---|
| Title | presence, character/pixel proxy length, duplicate within site, primary term presence rule | natural alignment to intent, clarity/non-clickbait quality |
| Meta description | presence/length, duplicate, forbidden markup | accurate summary, differentiating value |
| URL | scheme/path format, length, casing, slug policy, collision | semantic clarity only if enabled |
| H1 | exact count, presence, duplication | alignment with page purpose |
| H2/H3 | hierarchy/order, empty headings, min/max configured counts | coverage structure and usefulness |
| Keyword | normalized primary/secondary occurrence constraints, stuffing threshold policy | natural usage and semantic variants |
| Search intent | declared page/cluster intent consistency facts | whether content satisfies likely task/intent with evidence |
| Semantic coverage | required entity/term checklist if configured | topical completeness against brief/SERP/knowledge sources |
| Images | count/type/dimensions metadata, broken src | relevance of image plan |
| Alt text | missing/empty/length/duplicate/file-name-only checks | descriptive quality and context |
| Internal links | count ranges, self/broken/redirect links, orphan/in-degree, approved target policy | contextual relevance and placement |
| External links | scheme/status/domain allow/deny/nofollow policy | authority/relevance assessment |
| Schema | JSON-LD parse, allowed type/required properties, page consistency | content-to-schema semantic fit |
| Canonical | exactly one, normalized absolute URL, indexability and domain consistency | none initially |
| Breadcrumbs | structure/order/link validity and schema consistency | label clarity only if needed |
| FAQ | markup/content pair and required fields; no requirement unless applicable | question usefulness/non-duplication |
| CTA | configured presence/link/action metadata | fit with funnel stage and clarity |
| Readability | sentence/paragraph lengths, configured readability formula, jargon list | audience fit, coherence, clarity |

Length thresholds are project/locale/device policy parameters, not universal hardcoded SEO facts. Validators do not promise rankings.

## 4. Validation pipeline

```text
page + immutable content version + rendered metadata snapshot
-> resolve active applicable rule versions
-> parse one normalized ContentAnalysisDocument
-> deterministic evaluators (pure, parallel where safe)
-> optional AI evaluation jobs using bounded evidence
-> findings persisted by component
-> scorecard/readiness projection
-> human review and remediation
```

`ContentAnalysisDocument` includes title/meta/canonical/URL, structured heading tree, normalized text blocks/node IDs, links, images/alt, schema objects, brief/cluster/intent, and rendered-page evidence when available. Parse failures produce explicit analysis errors; they are never counted as passes.

Deterministic evaluators are pure functions of normalized input + rule version and produce stable fixtures. AI evaluators receive the rule, rubric, relevant content excerpts, intent/brief, source manifest, and structured output schema. They return confidence and cited evidence. Low confidence is `needs_review`, not failure. AI findings cannot override a deterministic result.

## 5. Scoring and gates

The UI shows counts and components first. If a composite score is useful, it is a transparent versioned projection:

```text
component_score = passed_applicable_weight / applicable_weight * 100
overall = weighted mean of configured component scores
```

Errors in evaluation reduce coverage and display `incomplete`; they do not silently lower or raise the score. Blocking deterministic findings can make `publish_ready=false` irrespective of numeric score. AI findings are advisory until a project explicitly promotes a specific rubric to an approval gate after evaluation. Every score response includes formula version, weights, excluded/not-applicable/error counts, and rule manifest.

## 6. Rule lifecycle

`draft -> in_review -> approved -> active -> superseded|archived`. Edits create a new version. Activation is a human-authorized service command and may schedule re-analysis; old analyses continue to reference old versions. System recommendations and learning candidates produce drafts only. A rule cannot become active through model output alone.

## 7. API and domain boundaries

- SEO domain owns rule validation/lifecycle and deterministic evaluator registry.
- Content domain owns canonical content and exposes normalized snapshots.
- Internal-linking domain owns graph integrity and supplies link facts.
- AI domain supplies provider calls but does not own SEO decisions.
- `GET/POST /projects/{project_id}/seo-rules`, activation command, `POST /seo/analyses`, and analysis retrieval follow [API.md](API.md).
- Long/rendered/AI analyses are jobs keyed by `(content_hash, rule_manifest_hash, evaluator_versions)`.

## 8. Tests and acceptance

Each deterministic rule requires boundary/table/property fixtures, Unicode/locale cases, malformed-input behavior, and a golden finding schema. Rule resolution tests cover applicability and conflicts. Integration tests prove exact version persistence, tenant isolation, idempotent reruns, and partial analyzer failure. AI rubric datasets cover pass/fail/ambiguous/adversarial examples with inter-reviewer baselines and versioned thresholds.

The engine is acceptable when results are reproducible, every finding points to evidence/remediation and exact versions, deterministic and AI results remain visually/data-model distinct, unavailable evaluators are visible, and active policy cannot change without authorized approval.

