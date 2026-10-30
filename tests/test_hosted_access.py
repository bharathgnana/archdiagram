"""Unit tests for hosted MCP access helpers (no MCP or Google SDK required)."""

import datetime as dt
import unittest
import json
import os
from unittest.mock import patch

from mcp_server.access import ApiKeyGate, FirestoreQuotaStore, InvalidApiKey, MonthlyQuotaExceeded, bearer_token, current_month, issue_api_key, key_digest, parse_api_key
from mcp_server import tools


class TestHostedAccess(unittest.TestCase):
    def test_issued_key_round_trips_and_is_random(self):
        issued = issue_api_key()
        key_id, secret = parse_api_key(issued.value)
        self.assertEqual(key_id, issued.key_id)
        self.assertEqual(secret, issued.secret)
        self.assertNotEqual(issue_api_key().value, issued.value)

    def test_malformed_keys_are_rejected(self):
        for value in ("", "adgm_only", "other_a_" + "x" * 32, "adgm_id_short"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidApiKey):
                    parse_api_key(value)

    def test_digest_is_keyed_and_deterministic(self):
        self.assertEqual(key_digest("secret", "pepper"), key_digest("secret", "pepper"))
        self.assertNotEqual(key_digest("secret", "pepper"), key_digest("secret", "other-pepper"))

    def test_bearer_header_is_required(self):
        self.assertEqual(bearer_token([(b"authorization", b"Bearer adgm_id_" + b"x" * 32)]), "adgm_id_" + "x" * 32)
        with self.assertRaises(InvalidApiKey):
            bearer_token([(b"authorization", b"Basic credentials")])

    def test_current_month_uses_utc(self):
        self.assertEqual(current_month(dt.datetime(2026, 10, 30, tzinfo=dt.UTC)), "2026-10")

    def test_generated_keys_always_parse(self):
        for _ in range(1000):
            issued = issue_api_key()
            self.assertEqual(parse_api_key(issued.value), (issued.key_id, issued.secret))

    def test_hosted_render_returns_content_and_rejects_local_paths(self):
        spec = json.dumps({"title": "test", "nodes": [{"id": "a", "shape": "start"}], "edges": []})
        with patch.dict(os.environ, {"PORT": "8080"}):
            self.assertFalse(tools.validate_spec("README.md")["ok"])
            self.assertFalse(tools.generate_diagram("README.md")["ok"])
            self.assertFalse(tools.generate_diagram(spec, out_path="out.svg")["ok"])
            svg = tools.generate_diagram(spec, "svg")
            self.assertTrue(svg["ok"], svg)
            self.assertIn("<svg", svg["content"])
            pptx = tools.generate_diagram(spec, "pptx")
            self.assertTrue(pptx["ok"], pptx)
            self.assertTrue(pptx["content_base64"].startswith("UEs"))


class TestGate(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_and_quota(self):
        class Store:
            async def consume(self, key_id, digest, month):
                if key_id == "limited":
                    raise MonthlyQuotaExceeded("limit reached")
                if key_id != "valid" or digest != key_digest("x" * 32, "pepper"):
                    raise InvalidApiKey("invalid")

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        gate = ApiKeyGate(app, Store(), "pepper")
        for token, expected in ((None, 401), ("adgm_wrong_" + "x" * 32, 401),
                                ("adgm_limited_" + "x" * 32, 429),
                                ("adgm_valid_" + "x" * 32, 200)):
            messages = []
            async def send(message):
                messages.append(message)
            headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
            await gate({"type": "http", "method": "POST", "path": "/mcp", "headers": headers}, None, send)
            self.assertEqual(messages[0]["status"], expected)


class TestQuotaStore(unittest.TestCase):
    def test_quota_increment_and_new_month_reset(self):
        class Store(FirestoreQuotaStore):
            def __init__(self, month, count):
                super().__init__("test-project")
                self.fields = {"active": {"booleanValue": True}, "secretHash": {"stringValue": "digest"},
                               "monthlyLimit": {"integerValue": "2"}, "usageMonth": {"stringValue": month},
                               "usageCount": {"integerValue": str(count)}}
            def _metadata_token(self):
                return "test"
            def _request(self, method, path, token, body=None):
                if path == ":beginTransaction":
                    return {"transaction": "transaction"}
                if method == "GET":
                    return {"name": "document", "updateTime": "timestamp", "fields": self.fields}
                self.fields = body["writes"][0]["update"]["fields"]
                return {}

        store = Store("2026-09", 2)
        store._consume_sync("key", "digest", "2026-10")
        self.assertEqual(store.fields["usageCount"]["integerValue"], "1")
        store._consume_sync("key", "digest", "2026-10")
        with self.assertRaises(MonthlyQuotaExceeded):
            store._consume_sync("key", "digest", "2026-10")


if __name__ == "__main__":
    unittest.main()
