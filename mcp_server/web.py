"""Small, read-only browser shell for the hosted MCP service.

The browser authenticates with Identity Platform; diagram requests still go
through the existing API-key and quota gate, independently of that login.
"""
from __future__ import annotations

import json
import os
import asyncio
import urllib.request
import urllib.parse
from pathlib import Path

from .access import ApiKeyGate
from .tools import generate_diagram

ASSETS = Path(__file__).parent / "web_assets"


def browser_identity(token: str, api_key: str) -> dict | None:
    """Have Identity Platform verify the token and the email ownership claim."""
    if not token or not api_key:
        return None
    url = "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + urllib.parse.quote(api_key, safe="")
    request = urllib.request.Request(url, data=json.dumps({"idToken": token}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            users = json.load(response).get("users", [])
        if (len(users) == 1 and users[0].get("localId") and users[0].get("email")
                and users[0].get("emailVerified") is True and not users[0].get("disabled")):
            return {"uid": users[0]["localId"], "email": users[0]["email"]}
    except (OSError, ValueError, KeyError):
        return None
    return None


def verify_browser_identity(token: str, api_key: str) -> bool:
    return browser_identity(token, api_key) is not None


class BrowserApp:
    def __init__(self, app, store=None, pepper=None):
        self.app = app
        self.render_gate = ApiKeyGate(self.render, store, pepper, paths=("/api/render",)) if store and pepper else None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope.get("path"), scope.get("method")
        if path == "/api/render" and method == "POST":
            token = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k.lower() == b"x-firebase-token"), "")
            valid = await asyncio.to_thread(verify_browser_identity, token, os.environ.get("ARCHDIAGRAM_FIREBASE_API_KEY", ""))
            if not valid:
                return await self.respond_json(send, 401, {"error": "Verified email sign-in required"})
            if not self.render_gate:
                return await self.respond_json(send, 503, {"error": "Buyer access is not configured"})
            return await self.render_gate(scope, receive, send)
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
                 "/assets/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if method == "GET" and path in files:
            name, content_type = files[path]
            body = (ASSETS / name).read_bytes()
        elif method == "GET" and path == "/api/browser-config":
            body = json.dumps({"apiKey": os.environ.get("ARCHDIAGRAM_FIREBASE_API_KEY", ""),
                               "authDomain": os.environ.get("ARCHDIAGRAM_AUTH_DOMAIN", ""),
                               "projectId": os.environ.get("GOOGLE_CLOUD_PROJECT", "")}).encode()
            content_type = "application/json"
        else:
            return await self.app(scope, receive, send)
        headers = [(b"content-type", content_type.encode()), (b"cache-control", b"no-store"),
                   (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def respond_json(send, status, payload):
        body = json.dumps(payload).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})

    async def render(self, scope, receive, send):
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if len(body) > 1024 * 1024:
                return await self.respond_json(send, 413, {"error": "Diagram specification is too large"})
            if not event.get("more_body", False):
                break
        try:
            request = json.loads(body)
            if not isinstance(request, dict) or not isinstance(request.get("spec"), dict):
                raise ValueError("A JSON specification object is required")
            fmt = request.get("format", "svg")
            if fmt not in ("svg", "drawio", "pptx", "vsdx", "html"):
                raise ValueError("Unsupported format")
        except (ValueError, TypeError):
            return await self.respond_json(send, 400, {"error": "Invalid diagram request"})
        result = await asyncio.to_thread(generate_diagram, request["spec"], fmt)
        return await self.respond_json(send, 200, result)
