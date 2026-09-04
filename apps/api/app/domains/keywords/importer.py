"""CSV parsing, validation, and ingestion pipeline for keywords."""

import csv
import io
from typing import Any

from app.core.errors import DomainError

MAX_CSV_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_CSV_ROW_COUNT = 50_000


def clean_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def parse_csv_keywords(
    file_content: bytes,
    filename: str = "keywords.csv",
) -> list[dict[str, Any]]:
    """Parse and validate CSV content into typed keyword row dictionaries."""
    max_mb = MAX_CSV_FILE_SIZE_BYTES // (1024 * 1024)
    if len(file_content) > MAX_CSV_FILE_SIZE_BYTES:
        raise DomainError(
            "FILE_TOO_LARGE",
            f"CSV file exceeds maximum permitted size of {max_mb}MB",
        )

    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_content.decode("latin-1")
        except Exception as exc:
            raise DomainError(
                "INVALID_ENCODING", "Unable to decode CSV file as UTF-8 or Latin-1"
            ) from exc

    stream = io.StringIO(text, newline="")
    reader = csv.reader(stream)

    try:
        raw_headers = next(reader)
    except StopIteration:
        raise DomainError("EMPTY_FILE", "The uploaded CSV file is empty.") from None

    headers = [clean_header(h) for h in raw_headers]

    col_keyword = -1
    col_volume = -1
    col_difficulty = -1
    col_cpc = -1
    col_intent = -1

    for idx, h in enumerate(headers):
        if h in ("keyword", "term", "query", "kw", "search_term"):
            col_keyword = idx
        elif h in (
            "volume",
            "search_volume",
            "monthly_volume",
            "searches",
            "avg_monthly_searches",
        ):
            col_volume = idx
        elif h in ("difficulty", "keyword_difficulty", "kd", "competition", "comp"):
            col_difficulty = idx
        elif h in ("cpc", "cost_per_click", "cpc_usd"):
            col_cpc = idx
        elif h in ("intent", "search_intent"):
            col_intent = idx

    if col_keyword == -1:
        raise DomainError(
            "MISSING_KEYWORD_COLUMN",
            "CSV file must contain a 'keyword' or 'query' column header.",
        )

    parsed_rows: list[dict[str, Any]] = []

    for row_idx, row in enumerate(reader, start=2):
        if row_idx > MAX_CSV_ROW_COUNT + 1:
            break
        if not row or not any(cell.strip() for cell in row):
            continue

        raw_kw = row[col_keyword].strip() if col_keyword < len(row) else ""
        if not raw_kw:
            continue

        volume = 0
        if col_volume != -1 and col_volume < len(row):
            val = row[col_volume].replace(",", "").replace("$", "").strip()
            try:
                volume = max(0, int(float(val))) if val else 0
            except ValueError:
                volume = 0

        difficulty = 0.0
        if col_difficulty != -1 and col_difficulty < len(row):
            val = row[col_difficulty].replace(",", "").replace("%", "").strip()
            try:
                difficulty = max(0.0, min(100.0, float(val))) if val else 0.0
            except ValueError:
                difficulty = 0.0

        cpc = 0.0
        if col_cpc != -1 and col_cpc < len(row):
            val = row[col_cpc].replace(",", "").replace("$", "").strip()
            try:
                cpc = max(0.0, float(val)) if val else 0.0
            except ValueError:
                cpc = 0.0

        intent = ""
        if col_intent != -1 and col_intent < len(row):
            intent = row[col_intent].strip().upper()

        parsed_rows.append(
            {
                "row_number": row_idx,
                "keyword": raw_kw,
                "volume": volume,
                "difficulty": difficulty,
                "cpc": cpc,
                "intent": intent,
                "raw": {headers[i]: row[i] for i in range(min(len(headers), len(row)))},
            }
        )

    return parsed_rows
