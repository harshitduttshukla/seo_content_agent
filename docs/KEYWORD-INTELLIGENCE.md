# Keyword Intelligence & Universe

## Normalization & Deduplication

All keyword strings are normalized deterministically before persistence or indexing:
1. Stripped of leading and trailing whitespace.
2. Unicode normalized (NFKC) and case-folded to lowercase.
3. Hyphens, dashes (`\u2010`–`\u2015`), and slashes converted to whitespace.
4. Non-alphanumeric punctuation stripped.
5. Internal multiple spaces collapsed into a single space.
6. A composite unique index on `(project_id, normalized_keyword)` guarantees zero duplicate records within a project.

---

## Deterministic Search Intent & Funnel Classification

Intent classification executes with a deterministic signal matcher:
- **`NAVIGATIONAL`** (BOFU): Triggered by brand modifiers, `login`, `portal`, `app`, `official`.
- **`LOCAL`** (BOFU): Triggered by geography and modifiers like `near me`, `in [city]`.
- **`TRANSACTIONAL`** (BOFU): Triggered by purchase intent: `buy`, `pricing`, `coupon`, `quote`, `hire`, `software license`.
- **`COMMERCIAL`** (MOFU): Triggered by evaluation intent: `best`, `review`, `vs`, `alternatives`, `top`, `comparison`.
- **`INFORMATIONAL`** (TOFU): Triggered by question words (`how`, `what`, `why`, `when`) or guide terms (`guide`, `tutorial`, `template`, `checklist`, `learn`).

---

## Scoring Formulas

### 1. Business Value Score (0 – 100)
Measures the commercial relevance of a keyword to the business:
$$\text{Base Score} = \begin{cases} 90.0 & \text{if Transactional} \\ 75.0 & \text{if Commercial} \\ 70.0 & \text{if Local} \\ 40.0 & \text{if Informational} \\ 20.0 & \text{if Navigational} \end{cases}$$
- **Strategy Match**: +15.0 bonus if the keyword matches products, services, or priority topics in the active strategy.
- **CPC Bonus**: $+\min(10.0, \log_{10}(\text{CPC} + 1.0) \times 8.0)$.

### 2. Priority Score (0 – 100)
A composite ranking score balancing search demand, ranking opportunity, and commercial value:
$$\text{Priority Score} = (\text{Volume}_{\text{norm}} \times 0.30) + (\text{Opportunity} \times 0.25) + (\text{Business Value} \times 0.35) + (\text{Intent Weight} \times 0.10)$$
where:
- $\text{Volume}_{\text{norm}} = \min(100.0, \frac{\log_{10}(\max(10, \text{Volume}))}{5.0} \times 100.0)$
- $\text{Opportunity} = 100.0 - \text{Keyword Difficulty}$
