"""
Async Odoo JSON-RPC client.

Uses the /jsonrpc endpoint (JSON equivalent of XML-RPC) with API key auth.
The API key substitutes the password in every call, so no session cookies
are required and the UID is cached after the first authenticate call.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class OdooClient:
    def __init__(self) -> None:
        self.url = os.environ["ODOO_URL"].rstrip("/")
        self.db = os.environ["ODOO_DB"]
        self.api_key = os.environ["ODOO_API_KEY"]
        self.user = os.environ["ODOO_USER"]
        self._uid: int | None = None
        self._http = httpx.AsyncClient(timeout=30.0)

    # ── low-level RPC ──────────────────────────────────────────────────────

    async def _call(self, service: str, method: str, args: list) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
        }
        resp = await self._http.post(f"{self.url}/jsonrpc", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            detail = (err.get("data") or {}).get("message", "")
            raise RuntimeError(
                f"Odoo RPC error {err.get('code')}: {err.get('message')}"
                + (f" — {detail}" if detail else "")
            )
        return data["result"]

    async def _uid_cached(self) -> int:
        if self._uid is None:
            result = await self._call(
                "common", "authenticate", [self.db, self.user, self.api_key, {}]
            )
            if not result:
                raise RuntimeError(
                    "Odoo authentication failed — verify ODOO_USER and ODOO_API_KEY"
                )
            self._uid = result
        return self._uid

    # ── public helpers ─────────────────────────────────────────────────────

    async def execute(
        self, model: str, method: str, args: list, kwargs: dict | None = None
    ) -> Any:
        uid = await self._uid_cached()
        return await self._call(
            "object",
            "execute_kw",
            [self.db, uid, self.api_key, model, method, args, kwargs or {}],
        )

    async def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        kw: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kw["fields"] = fields
        if order:
            kw["order"] = order
        return await self.execute(model, "search_read", [domain or []], kw)

    async def read(
        self,
        model: str,
        ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict]:
        kw: dict[str, Any] = {}
        if fields:
            kw["fields"] = fields
        return await self.execute(model, "read", [ids], kw)

    async def create(self, model: str, vals: dict) -> int:
        return await self.execute(model, "create", [vals])

    async def write(self, model: str, ids: list[int], vals: dict) -> bool:
        return await self.execute(model, "write", [ids, vals])

    async def unlink(self, model: str, ids: list[int]) -> bool:
        return await self.execute(model, "unlink", [ids])

    async def read_group(
        self,
        model: str,
        domain: list,
        fields: list[str],
        groupby: list[str],
        lazy: bool = False,
    ) -> list[dict]:
        return await self.execute(
            model, "read_group", [domain, fields, groupby], {"lazy": lazy}
        )

    async def close(self) -> None:
        await self._http.aclose()
