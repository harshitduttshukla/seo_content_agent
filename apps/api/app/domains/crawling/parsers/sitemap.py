"""XML Sitemap and Sitemap Index parser."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class SitemapEntry:
    loc: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


@dataclass(frozen=True)
class SitemapParseResult:
    is_index: bool
    child_sitemaps: list[str]
    urls: list[SitemapEntry]


class SitemapParser:
    @staticmethod
    def parse(xml_content: str | bytes) -> SitemapParseResult:
        """Parse sitemap XML content safely into URL entries or child sitemap links."""
        if not xml_content:
            return SitemapParseResult(is_index=False, child_sitemaps=[], urls=[])

        try:
            xml_bytes = xml_content.encode("utf-8") if isinstance(xml_content, str) else xml_content
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return SitemapParseResult(is_index=False, child_sitemaps=[], urls=[])

        # Strip namespace if present
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag == "sitemapindex":
            child_sitemaps: list[str] = []
            for sitemap_node in root.findall(".//{*}sitemap") or root.findall(".//sitemap"):
                loc_node = (
                    sitemap_node.find("{*}loc")
                    if sitemap_node.find("{*}loc") is not None
                    else sitemap_node.find("loc")
                )
                if loc_node is not None and loc_node.text:
                    child_sitemaps.append(loc_node.text.strip())
            return SitemapParseResult(is_index=True, child_sitemaps=child_sitemaps, urls=[])

        # Standard urlset
        entries: list[SitemapEntry] = []
        for url_node in root.findall(".//{*}url") or root.findall(".//url"):
            loc_node = (
                url_node.find("{*}loc")
                if url_node.find("{*}loc") is not None
                else url_node.find("loc")
            )
            if loc_node is None or not loc_node.text:
                continue

            loc = loc_node.text.strip()

            lastmod_node = (
                url_node.find("{*}lastmod")
                if url_node.find("{*}lastmod") is not None
                else url_node.find("lastmod")
            )
            lastmod = (
                lastmod_node.text.strip()
                if lastmod_node is not None and lastmod_node.text
                else None
            )

            changefreq_node = (
                url_node.find("{*}changefreq")
                if url_node.find("{*}changefreq") is not None
                else url_node.find("changefreq")
            )
            changefreq = (
                changefreq_node.text.strip()
                if changefreq_node is not None and changefreq_node.text
                else None
            )

            priority_node = (
                url_node.find("{*}priority")
                if url_node.find("{*}priority") is not None
                else url_node.find("priority")
            )
            priority: float | None = None
            if priority_node is not None and priority_node.text:
                try:
                    priority = float(priority_node.text.strip())
                except ValueError:
                    priority = None

            entries.append(
                SitemapEntry(loc=loc, lastmod=lastmod, changefreq=changefreq, priority=priority)
            )

        return SitemapParseResult(is_index=False, child_sitemaps=[], urls=entries)
