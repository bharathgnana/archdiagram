"""Hosted MCP API-key authentication and monthly quota enforcement.

This module deliberately uses only the standard library.  Cloud Run obtains an
OAuth access token from its metadata service and talks to Firestore's REST API,
so the core package remains dependency-free and the runtime needs no embedded
Google credential file.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


KEY_PREFIX = "adgm"
DEFAULT_MONTHLY_LIMIT = 1000
METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


class AccessError(RuntimeError):
    """Raised when a hosted request does not have usable access."""


class InvalidApiKey(AccessError):
    pass


class MonthlyQuotaExceeded(AccessError):
    pass


@dataclass(frozen=True)
class IssuedApiKey:
    """The only point at which an API-key secret is available."""

    key_id: str
    secret: str

    @property
    def value(self) -> str:
        return f"{KEY_PREFIX}_{self.key_id}_{self.secret}"


def issue_api_key() -> IssuedApiKey:
    """Create a random, URL-safe key. Persist only its keyed digest."""
    return IssuedApiKey(
        key_id=secrets.token_hex(9),
        secret=secrets.token_urlsafe(32).rstrip("="),
    )


def parse_api_key(value: str) -> tuple[str, str]:
    prefix, separator, remainder = value.strip().partition("_")
    if prefix != KEY_PREFIX or not separator:
        raise InvalidApiKey("Missing or malformed API key")
    key_id, separator, secret = remainder.partition("_")
    if not key_id or not separator or len(secret) < 32:
        raise InvalidApiKey("Missing or malformed API key")
    return key_id, secret


def key_digest(secret: str, pepper: str) -> str:
    if not pepper:
        raise ValueError("ARCHDIAGRAM_API_KEY_PEPPER must be set")
    return hmac.new(pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def current_month(now: dt.datetime | None = None) -> str:
    instant = now or dt.datetime.now(dt.UTC)
    return f"{instant.year:04d}-{instant.month:02d}"


def bearer_token(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and token:
                return token
    raise InvalidApiKey("Use Authorization: Bearer <API key>")


def _string(fields: dict[str, Any], name: str, default: str = "") -> str:
    return str(fields.get(name, {}).get("stringValue", default))


def _integer(fields: dict[str, Any], name: str, default: int = 0) -> int:
    return int(fields.get(name, {}).get("integerValue", default))


def _boolean(fields: dict[str, Any], name: str, default: bool = False) -> bool:
    return bool(fields.get(name, {}).get("booleanValue", default))


class FirestoreQuotaStore:
    """Consumes one request from a per-key monthly Firestore quota.

    A Firestore transaction makes the increment atomic across Cloud Run
    instances.  The runtime identity needs only ``roles/datastore.user``.
    """

    def __init__(self, project_id: str, database: str = "(default)", collection: str = "api_keys") -> None:
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for hosted access")
        self._project_id = project_id
        self._database = database
        self._collection = collection
        self._base_url = (
            f"https://firestore.googleapis.com/v1/projects/{urllib.parse.quote(project_id, safe='')}"
            f"/databases/{urllib.parse.quote(database, safe='()')}/documents"
        )

    async def consume(self, key_id: str, secret_digest: str, month: str) -> None:
        await asyncio.to_thread(self._consume_sync, key_id, secret_digest, month)

    def _metadata_token(self) -> str:
        request = urllib.request.Request(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
        try:
            with urllib.request.urlopen(request, timeout=3) as response:  # nosec B310 - fixed metadata URL
                return json.load(response)["access_token"]
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            raise AccessError("Hosted credential service is unavailable") from exc

    def _request(self, method: str, path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:  # nosec B310 - fixed Google API origin
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise InvalidApiKey("Unknown API key") from exc
            if exc.code == 409:
                raise AccessError("Concurrent quota update; retry the request") from exc
            raise AccessError("Access service is unavailable") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AccessError("Access service is unavailable") from exc

    def _consume_sync(self, key_id: str, secret_digest: str, month: str) -> None:
        token = self._metadata_token()
        encoded_path = f"/{self._collection}/{urllib.parse.quote(key_id, safe='')}"
        for _ in range(3):
            transaction = self._request("POST", ":beginTransaction", token).get("transaction")
            if not transaction:
                raise AccessError("Access service is unavailable")
            document = self._request("GET", f"{encoded_path}?transaction={urllib.parse.quote(transaction, safe='')}", token)
            fields = document.get("fields", {})
            if not _boolean(fields, "active"):
                raise InvalidApiKey("API key is inactive")
            expected = _string(fields, "secretHash")
            if not hmac.compare_digest(expected, secret_digest):
                raise InvalidApiKey("Unknown API key")
            limit = _integer(fields, "monthlyLimit", DEFAULT_MONTHLY_LIMIT)
            count = _integer(fields, "usageCount") if _string(fields, "usageMonth") == month else 0
            if count >= limit:
                raise MonthlyQuotaExceeded(f"Monthly request limit of {limit} reached")
            fields.update(
                {
                    "usageMonth": {"stringValue": month},
                    "usageCount": {"integerValue": str(count + 1)},
                }
            )
            write = {
                "update": {"name": document["name"], "fields": fields},
                "currentDocument": {"updateTime": document["updateTime"]},
            }
            try:
                self._request("POST", ":commit", token, {"writes": [write], "transaction": transaction})
                return
            except AccessError:
                continue
        raise AccessError("Concurrent quota update; retry the request")


class ApiKeyGate:
    """Raw ASGI middleware safe for streamable HTTP and SSE responses."""

    def __init__(self, app: Callable[..., Awaitable[None]], store: FirestoreQuotaStore, pepper: str, paths: tuple[str, ...] = ("/mcp",)) -> None:
        self.app = app
        self.store = store
        self.pepper = pepper
        self.paths = paths

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") not in self.paths or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        try:
            key_id, secret = parse_api_key(bearer_token(scope.get("headers", [])))
            await self.store.consume(key_id, key_digest(secret, self.pepper), current_month())
        except InvalidApiKey as exc:
            await self._respond(send, 401, str(exc))
            return
        except MonthlyQuotaExceeded as exc:
            await self._respond(send, 429, str(exc))
            return
        except AccessError as exc:
            await self._respond(send, 503, str(exc))
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _respond(send: Any, status: int, detail: str) -> None:
        body = json.dumps({"error": detail}).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


def hosted_access_settings() -> tuple[FirestoreQuotaStore, str]:
    """Load the Cloud Run-only settings, failing closed if misconfigured."""
    pepper = os.environ.get("ARCHDIAGRAM_API_KEY_PEPPER", "")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    database = os.environ.get("ARCHDIAGRAM_FIRESTORE_DATABASE", "(default)")
    return FirestoreQuotaStore(project_id, database), pepper
