# Deterministic Keyword Clustering Engine

## Clustering Philosophy

In our content operating system: **"Keywords are Not Pages"**.

A single webpage should target a semantic cluster of related queries rather than individual search terms. Our clustering engine groups keywords deterministically by analyzing token similarity and search intent.

---

## Similarity Metric

Two keywords $K_1$ and $K_2$ have their similarity $S(K_1, K_2) \in [0.0, 1.0]$ computed by:
1. **Tokenization & Stop Word Filtering**: Filter out English stop words, auxiliaries, and articles.
2. **Jaccard Similarity**:
   $$J(T_1, T_2) = \frac{|T_1 \cap T_2|}{|T_1 \cup T_2|}$$
3. **Root Overlap Ratio**: When the primary root tokens overlap significantly ($|T_1 \cap T_2| / \min(|T_1|, |T_2|) \ge 0.66$), a $+0.20$ bonus is added.
4. **Substring / Phrase Containment**: $+0.25$ bonus if one normalized phrase is completely contained inside the other.
5. **Intent Match**: $+0.15$ bonus if both keywords share the identical search intent.

Total similarity is clamped at $1.0$.

---

## Cluster Formation Algorithm

1. Sort all active project keywords descending by `(priority_score, search_volume)`.
2. Select the top unassigned keyword as the **Cluster Leader**.
3. Group all unassigned candidates with similarity $\ge \text{threshold}$ (default: $0.45$) into the cluster.
4. Designate the primary target keyword as the candidate with the highest search volume and priority score.
5. Generate an explainable rationale citing overlapping theme tokens.
6. Compute composite cluster score from member priority scores and cluster breadth.

---

## Governed Human-in-the-Loop Operations

- **Cluster Approval**: Clusters are created in `proposed` status and can be toggled to `reviewed`, `approved`, or `rejected`.
- **Merge Clusters**: Combine multiple clusters into a single unified cluster with designated primary keyword.
- **Move Keywords**: Reassign specific keywords from one cluster to another.
