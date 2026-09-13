"""Crawl frontier managing discovered URL queue, depth, deduplication, and priority."""

from collections import deque
from dataclasses import dataclass

from app.domains.crawling.security.url import is_same_domain, normalize_crawl_url


@dataclass
class FrontierItem:
    url: str
    normalized_url: str
    depth: int
    source: str  # "seed", "sitemap", "internal_link"
    priority: int = 0  # lower integer = higher priority


class CrawlFrontier:
    def __init__(
        self,
        base_host: str,
        max_depth: int = 5,
        max_pages: int = 500,
        include_subdomains: bool = False,
        allowed_paths: list[str] | None = None,
        blocked_paths: list[str] | None = None,
    ) -> None:
        self.base_host = base_host
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.include_subdomains = include_subdomains
        self.allowed_paths = allowed_paths or []
        self.blocked_paths = blocked_paths or []

        # Tracking sets
        self._seen_normalized_urls: set[str] = set()
        # High priority queue (sitemap / seed) and normal queue (discovered links)
        self._priority_queue: deque[FrontierItem] = deque()
        self._standard_queue: deque[FrontierItem] = deque()

    @property
    def total_seen(self) -> int:
        return len(self._seen_normalized_urls)

    @property
    def is_empty(self) -> bool:
        return len(self._priority_queue) == 0 and len(self._standard_queue) == 0

    def is_url_allowed(self, url: str) -> bool:
        """Check domain boundary and path allow/block lists."""
        if not is_same_domain(url, self.base_host, self.include_subdomains):
            return False

        if self.blocked_paths:
            for bp in self.blocked_paths:
                if bp and bp in url:
                    return False

        if self.allowed_paths:
            allowed = any(ap in url for ap in self.allowed_paths if ap)
            if not allowed:
                return False

        return True

    def add(self, url: str, depth: int, source: str = "internal_link") -> FrontierItem | None:
        """Add a discovered URL to the frontier if eligible and not already seen."""
        if depth > self.max_depth:
            return None

        if len(self._seen_normalized_urls) >= self.max_pages * 3:
            # Prevent frontier memory inflation beyond 3x page budget
            return None

        if len(url) > 2048:
            return None

        normalized = normalize_crawl_url(url)
        if len(normalized) > 2048 or not normalized.startswith(("http://", "https://")):
            return None

        if not self.is_url_allowed(normalized):
            return None

        if normalized in self._seen_normalized_urls:
            return None

        self._seen_normalized_urls.add(normalized)

        item = FrontierItem(
            url=url,
            normalized_url=normalized,
            depth=depth,
            source=source,
            priority=0 if source in ("seed", "sitemap") else 1,
        )

        if item.priority == 0:
            self._priority_queue.append(item)
        else:
            self._standard_queue.append(item)

        return item

    def pop_next(self) -> FrontierItem | None:
        """Pop the next URL item to crawl with priority ordering."""
        if self._priority_queue:
            return self._priority_queue.popleft()
        if self._standard_queue:
            return self._standard_queue.popleft()
        return None
