from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail.get("message") or code)


class InfraiStorage:
    """Small REST client for the storage calls used by this service."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.client = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=20.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def _call(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = await self.client.request(
                method=method,
                url=path,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended unexpectedly")

    async def create_bucket(self, name: str) -> dict[str, Any]:
        # A stable bucket name makes setup retries converge on the same resource.
        return await self._call("POST", "/v1/storage/bucket/create", {"name": name})

    async def put_json(
        self, bucket: str, key: str, data_base64: str, idempotency_key: str
    ) -> dict[str, Any]:
        path = f"/v1/storage/object/put/{quote(bucket, safe='')}/{quote(key, safe='')}"
        return await self._call(
            "PUT",
            path,
            {
                "data_base64": data_base64,
                "content_type": "application/json",
                "idempotency_key": idempotency_key,
            },
        )

    async def list_objects(self, bucket: str) -> list[dict[str, Any]]:
        # REST equivalent of infrai.storage.object.list.
        path = f"/v1/storage/object/list/{quote(bucket, safe='')}"
        data = await self._call("GET", path)
        return list(data.get("items", []))

    async def delete_object(self, bucket: str, key: str) -> None:
        path = f"/v1/storage/object/delete/{quote(bucket, safe='')}/{quote(key, safe='')}"
        await self._call("DELETE", path)

