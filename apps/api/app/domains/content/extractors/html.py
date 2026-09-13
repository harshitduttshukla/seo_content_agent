"""Deterministic HTML content, metadata, links, headings, and images extractor."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from app.domains.crawling.security.url import is_same_domain, normalize_crawl_url
from bs4 import BeautifulSoup, Comment, Tag


@dataclass(frozen=True)
class ExtractedHeading:
    level: int
    text: str
    order: int


@dataclass(frozen=True)
class ExtractedLink:
    target_url: str
    normalized_target_url: str
    anchor_text: str
    rel: str | None
    is_internal: bool
    nofollow: bool
    ugc: bool
    sponsored: bool


@dataclass(frozen=True)
class ExtractedImage:
    src: str
    alt: str
    title: str | None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class ExtractedPageContent:
    title: str
    meta_description: str
    canonical_url: str | None
    language: str
    headings: list[dict[str, object]]
    links: list[ExtractedLink]
    images: list[dict[str, object]]
    metadata: dict[str, object]
    cleaned_content: str
    structured_content: dict[str, object]
    word_count: int
    content_hash: str


def _attr_to_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return " ".join(str(item) for item in val).strip()
    return str(val).strip()


def _clean_str(val: Any, max_len: int | None = None) -> str:
    if val is None:
        return ""
    text = str(val).replace("\x00", "").strip()
    if max_len is not None and len(text) > max_len:
        return text[:max_len]
    return text


class HtmlContentExtractor:
    def __init__(self, base_host: str, include_subdomains: bool = False) -> None:
        self.base_host = base_host
        self.include_subdomains = include_subdomains

    def extract(self, html: str, page_url: str) -> ExtractedPageContent:
        """Extract structured metadata, clean prose, links, and headings from HTML."""
        if not html or not html.strip():
            empty_hash = hashlib.sha256(b"").hexdigest()
            return ExtractedPageContent(
                title="",
                meta_description="",
                canonical_url=None,
                language="en",
                headings=[],
                links=[],
                images=[],
                metadata={},
                cleaned_content="",
                structured_content={"type": "document", "blocks": []},
                word_count=0,
                content_hash=empty_hash,
            )

        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Title (max 500 chars, no null bytes)
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = _clean_str(title_tag.get_text(strip=True), max_len=500)

        # 2. Extract Language (max 20 chars)
        html_tag = soup.find("html")
        language = "en"
        if html_tag and isinstance(html_tag, Tag):
            lang_attr = _clean_str(html_tag.get("lang") or html_tag.get("xml:lang"), max_len=20)
            if lang_attr:
                language = lang_attr

        # 3. Extract Meta tags & OpenGraph
        meta_description = ""
        meta_dict: dict[str, object] = {}
        og_dict: dict[str, str] = {}
        twitter_dict: dict[str, str] = {}
        robots_meta = ""

        for meta in soup.find_all("meta"):
            name = _attr_to_str(meta.get("name") or meta.get("property")).lower()
            content = _attr_to_str(meta.get("content"))
            if not name or not content:
                continue

            if name in ("description", "meta_description"):
                meta_description = _clean_str(content, max_len=1000)
            elif name == "robots":
                robots_meta = _clean_str(content, max_len=500)
            elif name.startswith("og:"):
                og_dict[name] = _clean_str(content, max_len=1000)
            elif name.startswith("twitter:"):
                twitter_dict[name] = _clean_str(content, max_len=1000)

        meta_dict["robots"] = robots_meta
        meta_dict["open_graph"] = og_dict
        meta_dict["twitter"] = twitter_dict

        # Schema JSON-LD
        schema_data: list[object] = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    data = json.loads(script.string)
                    schema_data.append(data)
                except Exception:
                    pass
        if schema_data:
            meta_dict["schema_json_ld"] = schema_data

        # 4. Extract Canonical URL
        canonical_url: str | None = None
        canonical_tag = soup.find(
            "link", rel=lambda r: r and "canonical" in _attr_to_str(r).lower()
        )
        if canonical_tag and isinstance(canonical_tag, Tag):
            href = _attr_to_str(canonical_tag.get("href"))
            if href:
                normalized_canonical = normalize_crawl_url(href, base_url=page_url)
                if len(normalized_canonical) <= 2048:
                    canonical_url = _clean_str(normalized_canonical, max_len=2048)

        # 5. Extract Headings Hierarchy
        ordered_headings: list[dict[str, object]] = []
        h_order = 0
        for h_tag in soup.find_all(re.compile(r"^h[1-6]$")):
            text = h_tag.get_text(separator=" ", strip=True)
            if text:
                h_order += 1
                level = int(h_tag.name[1])
                ordered_headings.append(
                    {"level": level, "text": _clean_str(text, max_len=500), "order": h_order}
                )

        # 6. Extract Links
        links_list: list[ExtractedLink] = []
        seen_links: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = _attr_to_str(a_tag.get("href"))
            if not raw_href or raw_href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

            resolved_url = urljoin(page_url, raw_href)
            normalized_target = normalize_crawl_url(resolved_url)
            if not normalized_target.startswith(("http://", "https://")):
                continue

            if len(resolved_url) > 2048 or len(normalized_target) > 2048:
                continue

            anchor_text = _clean_str(a_tag.get_text(separator=" ", strip=True), max_len=500)
            rel_str = _clean_str(_attr_to_str(a_tag.get("rel")), max_len=120)
            rel_lower = rel_str.lower()

            is_internal = is_same_domain(
                normalized_target,
                allowed_host=self.base_host,
                include_subdomains=self.include_subdomains,
            )

            link_key = f"{normalized_target}|{anchor_text}"
            if link_key not in seen_links:
                seen_links.add(link_key)
                links_list.append(
                    ExtractedLink(
                        target_url=resolved_url,
                        normalized_target_url=normalized_target,
                        anchor_text=anchor_text,
                        rel=rel_str or None,
                        is_internal=is_internal,
                        nofollow="nofollow" in rel_lower,
                        ugc="ugc" in rel_lower,
                        sponsored="sponsored" in rel_lower,
                    )
                )

        # 7. Extract Images
        images_list: list[dict[str, object]] = []
        for img in soup.find_all("img", src=True):
            src_str = _attr_to_str(img.get("src"))
            src = _clean_str(urljoin(page_url, src_str), max_len=2048)
            alt = _clean_str(_attr_to_str(img.get("alt")), max_len=1000)
            img_title = _clean_str(_attr_to_str(img.get("title")), max_len=500)
            width_val = _attr_to_str(img.get("width"))
            height_val = _attr_to_str(img.get("height"))

            width_int: int | None = int(width_val) if width_val.isdigit() else None
            height_int: int | None = int(height_val) if height_val.isdigit() else None

            images_list.append(
                {
                    "src": src,
                    "alt": alt,
                    "title": img_title if img_title else None,
                    "width": width_int,
                    "height": height_int,
                }
            )

        # 8. Clean Content & Build Structured Blocks
        clean_soup = BeautifulSoup(html, "html.parser")

        for element in clean_soup.find_all(
            ["script", "style", "noscript", "svg", "video", "audio", "nav", "footer", "iframe"]
        ):
            element.decompose()

        for comment in clean_soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        blocks: list[dict[str, object]] = []
        for node in clean_soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]
        ):
            node_text = _clean_str(node.get_text(separator=" ", strip=True))
            if not node_text:
                continue

            if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                blocks.append(
                    {
                        "type": "heading",
                        "level": int(node.name[1]),
                        "text": node_text,
                    }
                )
            elif node.name in ("p", "blockquote"):
                blocks.append(
                    {
                        "type": "paragraph",
                        "text": node_text,
                    }
                )
            elif node.name == "li":
                blocks.append(
                    {
                        "type": "list_item",
                        "text": node_text,
                    }
                )

        # Plain text
        main_text = clean_soup.get_text(separator="\n", strip=True)
        cleaned_text = _clean_str(re.sub(r"\n\s*\n+", "\n\n", main_text))
        words = re.findall(r"\b\w+\b", cleaned_text)
        word_count = len(words)

        hash_payload = f"{title}\n{cleaned_text}".encode()
        content_hash = hashlib.sha256(hash_payload).hexdigest()

        return ExtractedPageContent(
            title=title,
            meta_description=meta_description,
            canonical_url=canonical_url,
            language=language,
            headings=ordered_headings,
            links=links_list,
            images=images_list,
            metadata=meta_dict,
            cleaned_content=cleaned_text,
            structured_content={"type": "document", "blocks": blocks},
            word_count=word_count,
            content_hash=content_hash,
        )
