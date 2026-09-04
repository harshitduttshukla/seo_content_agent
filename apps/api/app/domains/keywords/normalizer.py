"""Keyword normalization and deduplication utilities."""

import re
import unicodedata


def normalize_keyword(raw_keyword: str) -> str:
    """Normalize keyword for deterministic comparison and deduplication.

    - Strips leading/trailing whitespace
    - Normalizes Unicode (NFKC)
    - Lowercases text
    - Converts dashes, slashes, and punctuation to spaces
    - Collapses multiple whitespaces
    """
    if not raw_keyword:
        return ""
    normalized = unicodedata.normalize("NFKC", raw_keyword.strip().lower())
    # Replace dashes, hyphens, and slashes with space
    normalized = re.sub(r"[\u2010-\u2015\-_/]", " ", normalized)
    # Remove punctuation except word characters and spaces
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # Collapse multiple whitespaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
