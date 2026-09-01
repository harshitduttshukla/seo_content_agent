"""S3-compatible private object-storage contract."""

from datetime import timedelta
from typing import Protocol


class ObjectStorage(Protocol):
    async def put(self, *, key: str, body: bytes, content_type: str) -> None: ...

    async def get(self, *, key: str) -> bytes: ...

    async def delete(self, *, key: str) -> None: ...

    async def signed_download_url(self, *, key: str, expires_in: timedelta) -> str: ...
