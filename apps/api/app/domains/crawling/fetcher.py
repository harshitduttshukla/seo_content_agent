"""SSRF-safe, bounded async HTTP fetcher."""

import time
from dataclasses import dataclass

import httpx
from app.domains.crawling.security.ssrf import SSRFSecurityError, validate_safe_url

DEFAULT_USER_AGENT = "Antigravity-ContentAgent/1.0 (+https://example.com/bot)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_REDIRECTS = 5


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text_content: str
    raw_bytes: bytes
    response_time_ms: int
    redirect_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    headers: dict[str, str] | None = None

    @property
    def is_success(self) -> bool:
        return self.status_code >= 200 and self.status_code < 300 and self.error_code is None


class HttpFetcher:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = MAX_RESPONSE_BYTES,
        max_redirects: int = MAX_REDIRECTS,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL safely with SSRF protection, redirect validation, and byte limits."""
        start_time = time.monotonic()
        current_url = url
        redirect_history: list[str] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5"
            ),
            "Accept-Encoding": "gzip, deflate",
        }

        try:
            # Step 1: Pre-validate initial URL
            validate_safe_url(current_url)

            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                verify=True,
            ) as client:
                redirect_count = 0

                while True:
                    # Validate URL on each hop
                    validate_safe_url(current_url)

                    request = client.build_request("GET", current_url, headers=headers)
                    response = await client.send(request, stream=True)

                    try:
                        # Handle redirects manually to inspect target URL for SSRF
                        if response.is_redirect and "location" in response.headers:
                            redirect_count += 1
                            if redirect_count > self.max_redirects:
                                return FetchResult(
                                    url=url,
                                    final_url=current_url,
                                    status_code=response.status_code,
                                    content_type=response.headers.get("content-type", ""),
                                    text_content="",
                                    raw_bytes=b"",
                                    response_time_ms=int((time.monotonic() - start_time) * 1000),
                                    error_code="TOO_MANY_REDIRECTS",
                                    error_message=f"Exceeded max redirects ({self.max_redirects})",
                                )

                            location = response.headers["location"]
                            # Resolve relative redirect against current_url
                            next_url = str(response.url.join(location))
                            redirect_history.append(next_url)
                            current_url = next_url
                            await response.aclose()
                            continue

                        # Check content type
                        content_type = response.headers.get("content-type", "").lower()
                        status_code = response.status_code

                        # Stream content up to max_bytes
                        body_chunks = []
                        total_bytes = 0

                        async for chunk in response.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_bytes:
                                await response.aclose()
                                return FetchResult(
                                    url=url,
                                    final_url=current_url,
                                    status_code=status_code,
                                    content_type=content_type,
                                    text_content="",
                                    raw_bytes=b"",
                                    response_time_ms=int((time.monotonic() - start_time) * 1000),
                                    error_code="RESPONSE_TOO_LARGE",
                                    error_message=(
                                        f"Response exceeded size limit of {self.max_bytes} bytes"
                                    ),
                                )
                            body_chunks.append(chunk)

                        raw_bytes = b"".join(body_chunks)
                        # Decode text safely
                        encoding = response.encoding or "utf-8"
                        try:
                            text_content = raw_bytes.decode(encoding, errors="replace")
                        except Exception:
                            text_content = raw_bytes.decode("utf-8", errors="replace")

                        elapsed_ms = int((time.monotonic() - start_time) * 1000)
                        return FetchResult(
                            url=url,
                            final_url=current_url,
                            status_code=status_code,
                            content_type=content_type,
                            text_content=text_content,
                            raw_bytes=raw_bytes,
                            response_time_ms=elapsed_ms,
                            redirect_url=redirect_history[-1] if redirect_history else None,
                            headers=dict(response.headers),
                        )
                    finally:
                        await response.aclose()

        except SSRFSecurityError as exc:
            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=0,
                content_type="",
                text_content="",
                raw_bytes=b"",
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                error_code="SSRF_BLOCKED",
                error_message=str(exc),
            )
        except httpx.TimeoutException:
            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=0,
                content_type="",
                text_content="",
                raw_bytes=b"",
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                error_code="TIMEOUT",
                error_message=f"Request timed out after {self.timeout} seconds",
            )
        except httpx.ConnectError as exc:
            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=0,
                content_type="",
                text_content="",
                raw_bytes=b"",
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                error_code="CONNECTION_ERROR",
                error_message=f"Connection failed: {exc}",
            )
        except Exception as exc:
            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=0,
                content_type="",
                text_content="",
                raw_bytes=b"",
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                error_code="FETCH_FAILED",
                error_message=str(exc),
            )
