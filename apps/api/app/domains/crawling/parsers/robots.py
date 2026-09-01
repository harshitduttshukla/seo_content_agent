"""Robots.txt parser with wildcard and sitemap extraction support."""

import contextlib
import re
from urllib.parse import urlparse


class RobotsRule:
    def __init__(self, path_pattern: str, allow: bool) -> None:
        self.allow = allow
        clean_pattern = path_pattern.strip()
        escaped = re.escape(clean_pattern).replace(r"\*", ".*")
        if escaped.endswith(r"\$"):
            escaped = escaped[:-2] + "$"
        self.regex = re.compile(f"^{escaped}")
        self.pattern_length = len(clean_pattern)

    def matches(self, path: str) -> bool:
        return bool(self.regex.match(path))


class RobotsParser:
    def __init__(self, content: str = "") -> None:
        self.sitemaps: list[str] = []
        self.crawl_delay: float | None = None
        self._rules_by_agent: dict[str, list[RobotsRule]] = {"*": []}
        self.parse(content)

    def parse(self, content: str) -> None:
        if not content:
            return

        current_agents: list[str] = []
        for line in content.splitlines():
            line = line.split("#")[0].strip()
            if not line or ":" not in line:
                continue

            field, _, val = line.partition(":")
            field = field.strip().lower()
            val = val.strip()

            if field == "user-agent":
                agent = val.lower()
                current_agents.append(agent)
                if agent not in self._rules_by_agent:
                    self._rules_by_agent[agent] = []
            elif field == "sitemap":
                if val and val not in self.sitemaps:
                    self.sitemaps.append(val)
            elif field == "crawl-delay":
                with contextlib.suppress(ValueError):
                    self.crawl_delay = float(val)
            elif field in ("allow", "disallow") and current_agents:
                is_allow = field == "allow"
                if not val and not is_allow:
                    continue
                rule = RobotsRule(val or "/", allow=is_allow)
                for agent in current_agents:
                    self._rules_by_agent[agent].append(rule)

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Evaluate if an agent is permitted to fetch a given URL under robots rules."""
        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        agent_key = user_agent.lower()
        rules = self._rules_by_agent.get(agent_key)
        if not rules:
            rules = self._rules_by_agent.get("*", [])

        if not rules:
            return True

        matched_rules = [r for r in rules if r.matches(path)]
        if not matched_rules:
            return True

        matched_rules.sort(key=lambda r: (r.pattern_length, 1 if r.allow else 0), reverse=True)
        return matched_rules[0].allow
